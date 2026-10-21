#!/usr/bin/env python3
"""Validate review records, evidence links, numeric comparisons and signoff readiness.

Python 3.10+ standard library only. This does not authenticate people or assess design safety.
"""
import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

DISCIPLINES = {'architecture', 'fire', 'structure', 'water', 'hvac', 'electrical', 'energy', 'coordination'}
CHECK_STATES = {'evaluated', 'not_applicable', 'insufficient_input', 'unsupported', 'unverified_basis', 'error'}
UNITS = {
    'mm': ('length', '0.001'), 'cm': ('length', '0.01'), 'm': ('length', '1'),
    'mm2': ('area', '0.000001'), 'm2': ('area', '1'), 'm²': ('area', '1'),
    'm3': ('volume', '1'), 'm³': ('volume', '1'), 'L': ('volume', '0.001'),
    'Pa': ('pressure', '1'), 'kPa': ('pressure', '1000'), 'MPa': ('pressure', '1000000'),
    'W': ('power', '1'), 'kW': ('power', '1000'),
    'N': ('force', '1'), 'kN': ('force', '1000'),
    'L/s': ('volume_flow', '0.001'), 'm3/s': ('volume_flow', '1'),
    's': ('time', '1'), 'min': ('time', '60'), 'h': ('time', '3600'),
    '%': ('ratio', '0.01'), 'ratio': ('ratio', '1'),
}

class Validator:
    def __init__(self, data, root=None, verify_files=False):
        self.data = data
        self.root = Path(root).resolve() if root is not None else None
        self.verify_files = verify_files
        self.errors, self.blockers = [], []
        self.sources, self.bases, self.rules, self.checks = {}, {}, {}, {}
        self.review_date, self.baseline_date = None, None
        self.synthetic = False

    def error(self, message):
        self.errors.append(message)

    def block(self, message):
        self.blockers.append(message)

    def obj(self, value, label):
        if not isinstance(value, dict):
            self.error(f'{label}: expected object')
            return {}
        return value

    def array(self, value, label, nonempty=False):
        if not isinstance(value, list):
            self.error(f'{label}: expected array')
            return []
        if nonempty and not value:
            self.error(f'{label}: must not be empty')
        return value

    def text(self, value, label):
        if not isinstance(value, str) or not value.strip():
            self.error(f'{label}: nonempty string required')
            return ''
        return value

    def fields(self, obj, names, label):
        for name in names.split():
            self.text(obj.get(name), f'{label}.{name}')

    def enum(self, value, allowed, label):
        if not isinstance(value, str) or value not in allowed:
            self.error(f'{label}: expected one of {sorted(allowed)}')
            return None
        return value

    def date(self, value, label, optional=False):
        if value is None and optional:
            return None
        try:
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError()
            return date.fromisoformat(value)
        except ValueError:
            self.error(f'{label}: expected valid ISO date YYYY-MM-DD')
            return None

    def timestamp(self, value, label):
        try:
            if not isinstance(value, str) or 'T' not in value:
                raise ValueError()
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                raise ValueError()
            if self.review_date and dt.date() > self.review_date:
                raise ValueError()
            return dt
        except ValueError:
            self.error(f'{label}: valid timezone-aware timestamp no later than review_date required')
            return None

    def number(self, value, label):
        try:
            if isinstance(value, bool) or not isinstance(value, (str, float, int)):
                raise ValueError()
            n = Decimal(str(value))
            if not n.is_finite():
                raise ValueError()
            return n
        except (ValueError, InvalidOperation):
            self.error(f'{label}: finite decimal number required')
            return None

    def ids(self, value, label, index=None, nonempty=False):
        items = self.array(value, label, nonempty)
        result = []
        for i, item in enumerate(items):
            item = self.text(item, f'{label}[{i}]')
            if item in result:
                self.error(f'{label}: duplicate ID {item}')
            if index is not None and item not in index:
                self.error(f'{label}: unknown reference {item}')
            result.append(item)
        return result

    def index(self, value, label):
        result = {}
        for i, raw in enumerate(self.array(value, label)):
            record = self.obj(raw, f'{label}[{i}]')
            key = self.text(record.get('id'), f'{label}[{i}].id')
            if key in result:
                self.error(f'{label}: duplicate ID {key}')
            result[key] = record
        return result

    def evidence(self, value, label, nonempty=True):
        result = self.array(value, label, nonempty)
        for i, raw in enumerate(result):
            e = self.obj(raw, f'{label}[{i}]')
            self.fields(e, 'source_id source_sha256 locator excerpt', f'{label}[{i}]')
            sid = e.get('source_id')
            source = self.sources.get(sid) if isinstance(sid, str) else None
            if source is None:
                self.error(f'{label}[{i}]: unknown source')
            elif e.get('source_sha256') != source.get('sha256'):
                self.error(f'{label}[{i}]: evidence hash differs from declared source {sid}')
        return result

    def usable_basis(self, basis):
        if basis.get('applicability') != 'confirmed':
            return False
        if self.synthetic and basis.get('status') == 'synthetic' and basis.get('authority') == 'synthetic':
            return True
        if basis.get('status') in ('unknown', 'synthetic') or basis.get('authority') == 'unknown':
            return False
        if basis.get('kind') == 'standard':
            if basis.get('authority') != 'official':
                return False
            try:
                start = date.fromisoformat(basis.get('effective_from', ''))
                end = date.fromisoformat(basis['effective_to']) if basis.get('effective_to') else None
            except (ValueError, TypeError):
                return False
            in_range = self.baseline_date is not None and start <= self.baseline_date and (end is None or self.baseline_date < end)
            return (basis.get('status') == 'effective' and in_range) or bool(basis.get('transition_ref'))
        return basis.get('status') == 'effective'

    def verify_source(self, sid, source):
        if self.root is None:
            self.error('File verification requires an explicit or review-file root')
            return
        raw = source.get('path')
        if not isinstance(raw, str) or not raw:
            return
        try:
            p = Path(raw)
            p = (p if p.is_absolute() else self.root / p).resolve(strict=True)
            if not p.is_relative_to(self.root):
                raise ValueError('source escapes the authorized root (including symlink target)')
            if not p.is_file():
                raise ValueError('source is not a regular file')
            h = hashlib.sha256()
            before = p.stat()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            after = p.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('source changed while being hashed')
            if h.hexdigest() != source.get('sha256'):
                raise ValueError('current bytes differ from recorded SHA-256; reopen affected checks')
        except (OSError, ValueError) as exc:
            self.error(f'sources.{sid}: {exc}')

    def compare(self, raw, rule, check, label):
        c = self.obj(raw, label)
        criterion = rule.get('criterion', {})
        self.fields(c, 'quantity object_ref observed_unit normalized_unit operator threshold_unit conditions_ref', label)
        if c.get('quantity') != criterion.get('quantity'):
            self.error(f'{label}: quantity differs from rule')
        if c.get('conditions_verified') is not True:
            self.error(f'{label}: applicability conditions were not verified')
        for field, expected in [('operator', criterion.get('operator')), ('normalized_unit', criterion.get('unit')), ('threshold_unit', criterion.get('unit'))]:
            if c.get(field) != expected:
                self.error(f'{label}.{field}: differs from rule')
        observed = self.number(c.get('observed_value'), label+'.observed_value')
        normalized = self.number(c.get('normalized_value'), label+'.normalized_value')
        threshold = self.number(c.get('threshold'), label+'.threshold')
        expected_threshold = self.number(criterion.get('threshold'), label+'.rule_threshold')
        if threshold != expected_threshold:
            self.error(f'{label}: comparison threshold differs from rule')
        ei = c.get('evidence_index')
        evidence = check.get('evidence')
        if isinstance(ei, bool) or not isinstance(ei, int) or not isinstance(evidence, list) or not 0 <= ei < len(evidence):
            self.error(f'{label}: evidence_index does not point to design evidence')
        source_unit = UNITS.get(c.get('observed_unit')) if isinstance(c.get('observed_unit'), str) else None
        dest_unit = UNITS.get(c.get('normalized_unit')) if isinstance(c.get('normalized_unit'), str) else None
        if source_unit is None or dest_unit is None or source_unit[0] != dest_unit[0]:
            self.error(f'{label}: unknown or incompatible units; use a supported explicit unit or record unsupported')
            return
        if observed is not None and normalized is not None:
            converted = observed * Decimal(source_unit[1]) / Decimal(dest_unit[1])
            if converted != normalized:
                self.error(f'{label}: normalized_value is inconsistent with explicit unit conversion')
        if normalized is None or threshold is None:
            return
        tolerance = self.number(criterion.get('tolerance', 0), label+'.tolerance')
        if tolerance is None:
            return
        op = c.get('operator')
        results = {'ge': normalized >= threshold, 'le': normalized <= threshold,
                   'gt': normalized > threshold, 'lt': normalized < threshold,
                   'eq': abs(normalized-threshold) <= tolerance}
        if isinstance(op, str) and op in results:
            expected = 'no_signal' if results[op] else 'signal'
            if check.get('result') != expected:
                self.error(f'{label}: result contradicts the recorded numeric comparison (expected {expected})')

    def run(self):
        d = self.obj(self.data, 'review')
        if d.get('schema_version') != '1.0':
            self.error('schema_version must be 1.0')
        self.enum(d.get('mode'), {'project', 'synthetic'}, 'mode')
        self.synthetic = d.get('mode') == 'synthetic'
        p = self.obj(d.get('project'), 'project')
        self.fields(p, 'id name region building_type stage baseline_id scope_ref', 'project')
        self.review_date = self.date(p.get('review_date'), 'project.review_date')
        self.baseline_date = self.date(p.get('baseline_date'), 'project.baseline_date')
        if self.review_date and self.baseline_date and self.baseline_date > self.review_date:
            self.error('baseline_date cannot be later than review_date')
        disciplines = self.ids(p.get('requested_disciplines'), 'project.requested_disciplines', nonempty=True)
        for di in disciplines:
            self.enum(di, DISCIPLINES, 'project.requested_disciplines')
        planned = self.ids(p.get('planned_check_ids'), 'project.planned_check_ids', nonempty=True)
        classification = self.enum(p.get('data_class'), {'public', 'internal', 'restricted', 'unclassified'}, 'project.data_class')
        processing = self.obj(p.get('processing'), 'project.processing')
        mode = self.enum(processing.get('mode'), {'local', 'cloud'}, 'project.processing.mode')
        if not isinstance(processing.get('environment_verified'), bool):
            self.error('processing.environment_verified must be boolean')
        if processing.get('environment_verified') is not True:
            self.block('Processing environment has no recorded verification')
        if classification == 'unclassified':
            self.block('Data classification is unresolved')
        if classification in {'restricted', 'unclassified'} and mode == 'cloud':
            self.error('Restricted or unclassified material cannot be routed to cloud in this contract')
        if classification in {'internal', 'restricted'} and not processing.get('authorization_ref'):
            self.block('Missing scoped processing authorization record')
        if classification == 'internal' and mode == 'cloud' and not processing.get('sanitization_ref'):
            self.error('Internal cloud processing requires a sanitization record and scoped authorization')

        self.sources = self.index(d.get('sources'), 'sources')
        self.bases = self.index(d.get('bases'), 'bases')
        self.rules = self.index(d.get('rules'), 'rules')
        self.checks = self.index(d.get('checks'), 'checks')
        findings = self.index(d.get('findings'), 'findings')
        if not self.sources:
            self.block('No declared design sources')
        for sid, s in self.sources.items():
            label = 'sources.'+sid
            self.fields(s, 'path sha256 revision locator_convention', label)
            if not isinstance(s.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', s.get('sha256', '')):
                self.error(label+': SHA-256 must have 64 lowercase hexadecimal characters')
            self.enum(s.get('discipline'), DISCIPLINES | {'general'}, label+'.discipline')
            self.enum(s.get('capability'), {'text', 'image', 'geometry', 'calculation', 'model', 'unreadable'}, label+'.capability')
            if self.verify_files:
                self.verify_source(sid, s)
        if not self.verify_files:
            self.block('Source file bytes have not been rehashed in this validation run')

        for bid, b in self.bases.items():
            label = 'bases.'+bid
            unknown = b.get('status') == 'unknown'
            self.fields(b, 'title summary' if unknown else 'title identifier clause source_ref verified_by rights_basis summary', label)
            if unknown:
                for field in ('identifier', 'clause', 'source_ref', 'verified_by', 'rights_basis'):
                    if b.get(field) is not None:
                        self.text(b[field], label+'.'+field)
            kind = self.enum(b.get('kind'), {'standard', 'project', 'drawing'}, label+'.kind')
            self.enum(b.get('authority'), {'official', 'project_approved', 'synthetic', 'unknown'}, label+'.authority')
            self.enum(b.get('status'), {'effective', 'superseded', 'future', 'unknown', 'synthetic'}, label+'.status')
            self.enum(b.get('applicability'), {'confirmed', 'unknown', 'not_applicable'}, label+'.applicability')
            vd = self.date(b.get('verified_at'), label+'.verified_at', optional=unknown)
            start = self.date(b.get('effective_from'), label+'.effective_from', optional=kind!='standard' or unknown)
            end = self.date(b.get('effective_to'), label+'.effective_to', optional=True)
            if vd and self.review_date and vd > self.review_date:
                self.error(label+': verification date is later than review_date')
            if start and end and end <= start:
                self.error(label+': invalid effective interval')
            identifier = b.get('identifier')
            if not self.synthetic and (b.get('authority') == 'synthetic' or b.get('status') == 'synthetic' or (isinstance(identifier,str) and identifier.startswith('EX-'))):
                self.error(label+': synthetic basis must not be used in a real project')

        for rid, r in self.rules.items():
            label = 'rules.'+rid
            self.fields(r, 'version', label)
            self.enum(r.get('discipline'), DISCIPLINES, label+'.discipline')
            self.enum(r.get('status'), {'draft', 'verified', 'disabled'}, label+'.status')
            self.ids(r.get('basis_ids'), label+'.basis_ids', self.bases, nonempty=True)
            app = self.obj(r.get('applicability'), label+'.applicability')
            self.enum(app.get('state'), {'confirmed', 'unknown', 'not_applicable'}, label+'.applicability.state')
            self.fields(app, 'rationale', label+'.applicability')
            criterion = self.obj(r.get('criterion'), label+'.criterion')
            self.fields(criterion, 'quantity object_scope explanation', label+'.criterion')
            if r.get('status') == 'verified' or criterion.get('basis_locator') is not None:
                self.fields(criterion, 'basis_locator', label+'.criterion')
            kind = self.enum(criterion.get('kind'), {'numeric', 'qualitative', 'consistency', 'completeness'}, label+'.criterion.kind')
            if kind == 'numeric':
                if r.get('status') == 'verified' or criterion.get('operator') is not None:
                    self.enum(criterion.get('operator'), {'ge','le','gt','lt','eq'}, label+'.criterion.operator')
                if r.get('status') == 'verified' or criterion.get('unit') is not None:
                    self.fields(criterion, 'unit', label+'.criterion')
                if r.get('status') == 'verified' or criterion.get('threshold') is not None:
                    self.number(criterion.get('threshold'), label+'.criterion.threshold')
                tol = self.number(criterion.get('tolerance', 0), label+'.criterion.tolerance')
                if tol is not None and tol < 0:
                    self.error(label+': tolerance cannot be negative')
                if 'tolerance' in criterion and criterion.get('operator') != 'eq':
                    self.error(label+': tolerance is only supported with explicit eq criterion')
            if r.get('status') == 'verified':
                self.fields(r, 'verified_by verification_ref test_ref', label)
                rd = self.date(r.get('verified_at'), label+'.verified_at')
                if rd and self.review_date and rd > self.review_date:
                    self.error(label+': rule verification is later than review_date')

        if set(planned) != set(self.checks):
            self.error('planned_check_ids must exactly match recorded checks; missing and extra items cannot be hidden')
        for cid, c in self.checks.items():
            label = 'checks.'+cid
            rid = c.get('rule_id')
            rule = self.rules.get(rid) if isinstance(rid, str) else None
            if rule is None:
                self.error(label+': unknown rule_id')
                rule = {}
            source_ids = self.ids(c.get('source_ids'), label+'.source_ids', self.sources, nonempty=True)
            status = self.enum(c.get('status'), CHECK_STATES, label+'.status')
            self.fields(c, 'reason', label)
            evidence = self.evidence(c.get('evidence'), label+'.evidence', nonempty=status=='evaluated')
            for e in evidence:
                if isinstance(e, dict) and e.get('source_id') not in source_ids:
                    self.error(label+': evidence source is absent from source_ids')
            if status == 'evaluated':
                self.enum(c.get('result'), {'signal','no_signal'}, label+'.result')
                if any(self.sources.get(sid, {}).get('capability') == 'unreadable' for sid in source_ids):
                    self.error(label+': unreadable source cannot support an evaluated check')
                if rule.get('status') != 'verified' or self.obj(rule.get('applicability'), label+'.rule.applicability').get('state') != 'confirmed':
                    self.error(label+': evaluated check requires a verified, applicable rule')
                for bid in rule.get('basis_ids', []) if isinstance(rule.get('basis_ids'),list) else []:
                    b = self.bases.get(bid) if isinstance(bid,str) else None
                    if b is None or not self.usable_basis(b):
                        self.error(label+': evaluated check uses unverified or inapplicable basis')
                if isinstance(rule.get('criterion'),dict) and rule['criterion'].get('kind') == 'numeric':
                    self.compare(c.get('comparison'), rule, c, label+'.comparison')
            else:
                if c.get('result') is not None or c.get('comparison') is not None:
                    self.error(label+': unevaluated check cannot claim a result or comparison')
                if status != 'not_applicable':
                    self.block(label+': '+str(status))

        signal_findings = set()
        for fid, f in findings.items():
            label = 'findings.'+fid
            self.fields(f, 'check_id title observation suggested_action', label)
            cid = f.get('check_id')
            check = self.checks.get(cid) if isinstance(cid,str) else None
            if check is None:
                self.error(label+': unknown check_id')
                check = {}
            elif check.get('status')=='evaluated' and check.get('result')=='signal':
                signal_findings.add(cid)
            self.enum(f.get('discipline'), DISCIPLINES, label+'.discipline')
            rid = check.get('rule_id')
            rule = self.rules.get(rid, {}) if isinstance(rid,str) else {}
            if rule and f.get('discipline') != rule.get('discipline'):
                self.error(label+': discipline differs from check rule')
            kind = self.enum(f.get('kind'), {'rule_deviation','document_conflict','missing_information'}, label+'.kind')
            if kind == 'rule_deviation' and not (check.get('status') == 'evaluated' and check.get('result') == 'signal'):
                self.error(label+': rule_deviation requires evaluated signal')
            self.enum(f.get('priority'), {'P1','P2','P3'}, label+'.priority')
            self.enum(f.get('confidence'), {'high','medium','low'}, label+'.confidence')
            basis_ids = self.ids(f.get('basis_ids'), label+'.basis_ids', self.bases, nonempty=True)
            rule_bases = rule.get('basis_ids', [])
            if isinstance(rule_bases, list) and any(isinstance(bid, str) and bid not in basis_ids for bid in rule_bases):
                self.error(label+': finding omits a basis required by its rule')
            for bid in basis_ids:
                if bid in self.bases and not self.usable_basis(self.bases[bid]):
                    self.error(label+': finding uses unverified basis; record a gap instead')
            ev = self.evidence(f.get('evidence'), label+'.evidence')
            if kind == 'document_conflict' and len({e.get('source_id') for e in ev if isinstance(e,dict) and isinstance(e.get('source_id'),str)}) < 2:
                self.error(label+': document_conflict requires two distinct design sources')
            review = self.obj(f.get('review'), label+'.review')
            rs = self.enum(review.get('status'), {'pending','adopted','not_applicable','undetermined'}, label+'.review.status')
            if rs != 'pending' and rs is not None:
                self.fields(review, 'actor record_ref note', label+'.review')
                self.timestamp(review.get('at'), label+'.review.at')
            if rs == 'not_applicable' and review.get('baseline_id') != p.get('baseline_id'):
                self.error(label+': not_applicable disposition must refer to the current baseline')
            closure = self.obj(f.get('closure'), label+'.closure')
            cs = self.enum(closure.get('status'), {'open','response_submitted','recheck_required','closed','not_applicable'}, label+'.closure.status')
            revised = self.ids(closure.get('revision_source_ids'), label+'.closure.revision_source_ids', self.sources)
            if cs == 'closed':
                if rs != 'adopted':
                    self.error(label+': closed requires an adopted human disposition')
                self.fields(closure, 'response', label+'.closure')
                if not revised:
                    self.error(label+': closed requires revision sources')
                recheck = self.obj(closure.get('recheck'), label+'.closure.recheck')
                self.fields(recheck, 'actor record_ref baseline_id', label+'.closure.recheck')
                self.timestamp(recheck.get('at'), label+'.closure.recheck.at')
                if recheck.get('baseline_id') != p.get('baseline_id'):
                    self.error(label+': closure recheck belongs to a different baseline')
                cev = self.evidence(recheck.get('evidence'), label+'.closure.recheck.evidence')
                if not any(isinstance(e,dict) and e.get('source_id') in revised for e in cev):
                    self.error(label+': recheck evidence must reference a revision source')
            elif cs == 'not_applicable':
                if rs != 'not_applicable':
                    self.error(label+': not_applicable closure requires a human not_applicable disposition')
            else:
                self.block(label+': issue remains '+str(cs))
            if rs in {'pending','undetermined'}:
                self.block(label+': human disposition is '+rs)

        for cid, c in self.checks.items():
            if c.get('status') == 'evaluated' and c.get('result') == 'signal' and cid not in signal_findings:
                self.error('checks.'+cid+': signal has no linked finding')
        states = Counter(c.get('status') for c in self.checks.values() if isinstance(c.get('status'),str))
        evaluated = states.get('evaluated', 0)
        if evaluated == 0:
            self.block('No checks were actually evaluated')
        for di in disciplines:
            relevant = [c for c in self.checks.values() if isinstance(c.get('rule_id'),str) and self.rules.get(c['rule_id'],{}).get('discipline') == di]
            if not relevant:
                self.block('Requested discipline has no planned checks: '+di)
        n = len(planned)
        applicable = n - states.get('not_applicable', 0)
        ready = not self.errors and not self.blockers
        return {'schema_valid': not self.errors, 'source_files_verified': self.verify_files and bool(self.sources) and not any(e.startswith('sources.') for e in self.errors),
                'mode': 'synthetic' if self.synthetic else 'project',
                'signoff_readiness': 'ready_for_human_signoff' if ready else 'blocked',
                'stats': {'rules_loaded': len(self.rules), 'planned': n, 'recorded_checks': len(self.checks),
                          'status_counts': dict(states), 'evaluated': evaluated, 'findings': len(findings),
                          'evaluated_rate': evaluated/n if n else None,
                          'applicable_evaluated_rate': evaluated/applicable if applicable>0 else None},
                'errors': self.errors, 'blockers': list(dict.fromkeys(self.blockers)),
                'limits': 'Record and numeric consistency only; does not verify scope completeness, design safety, human identity, authorization content, signatures or network isolation.'}

def validate(data, root=None, verify_files=False):
    return Validator(data, root, verify_files).run()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('review', type=Path)
    ap.add_argument('--root', type=Path)
    ap.add_argument('--verify-files', action='store_true')
    ap.add_argument('--gate', action='store_true', help='Verify files and require no preparation blockers; never a legal signoff')
    args = ap.parse_args()
    try:
        data = json.loads(args.review.read_text(encoding='utf-8'))
        result = validate(data, args.root or args.review.parent, args.verify_files or args.gate)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if result['errors'] else 3 if args.gate and result['blockers'] else 0
    except (OSError, ValueError) as exc:
        ap.exit(2, f'Validation failed: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
