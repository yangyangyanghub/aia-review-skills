#!/usr/bin/env python3
"""Check the published skill catalog, YAML metadata and local resource links."""
import json
from pathlib import Path
import re
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]

def main():
    errors=[]
    catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
    skill_files=sorted((ROOT/'skills').glob('*/SKILL.md'))
    declared=[entry['name'] for entry in catalog]
    actual=[p.parent.name for p in skill_files]
    if len(actual)!=15 or len(declared)!=15 or len(set(declared))!=15 or set(declared)!=set(actual):
        errors.append('The catalog and directories must contain the same 15 unique skills')
    links=0
    for skill in skill_files:
        name=skill.parent.name
        content=skill.read_text(encoding='utf-8')
        front=re.match(r'^---\n(.*?)\n---(?:\n|$)',content,re.DOTALL)
        if front is None:
            errors.append(f'{name}: missing YAML frontmatter')
            continue
        metadata=yaml.safe_load(front.group(1))
        if not isinstance(metadata,dict) or metadata.get('name')!=name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64:
            errors.append(f'{name}: invalid skill name or frontmatter')
            continue
        description=metadata.get('description')
        if not isinstance(description,str) or not description.strip() or len(description)>1024:
            errors.append(f'{name}: invalid description')
        entry=next((entry for entry in catalog if entry['name']==name),{})
        if entry.get('description')!=description:
            errors.append(f'{name}: catalog description differs from SKILL.md')
        ui=yaml.safe_load((skill.parent/'agents/openai.yaml').read_text(encoding='utf-8'))
        interface=ui.get('interface',{}) if isinstance(ui,dict) else {}
        short=interface.get('short_description')
        prompt=interface.get('default_prompt')
        if not isinstance(short,str) or not 25<=len(short)<=64:
            errors.append(f'{name}: short_description must contain 25–64 characters')
        if not isinstance(prompt,str) or '$'+name not in prompt:
            errors.append(f'{name}: default_prompt must reference its skill')
    for doc in sorted(ROOT.rglob('*.md')):
        if '.git' in doc.relative_to(ROOT).parts or doc.name in {'AGENTS.md','TASK.md','PUBLISH.md'}:
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):
                continue
            path=(doc.parent/target.split('#')[0]).resolve()
            if not path.is_relative_to(ROOT) or not path.exists():
                errors.append(f'{doc.relative_to(ROOT)}: unresolved or external local resource {target}')
            links+=1
    print(json.dumps({'skills':len(actual),'resource_links':links,'errors':errors},ensure_ascii=False,indent=2))
    return 1 if errors else 0

if __name__=='__main__':
    sys.exit(main())
