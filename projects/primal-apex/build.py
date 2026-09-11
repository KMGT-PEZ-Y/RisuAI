"""Build exactly four independent RisuAI modules (Python standard library only)."""
from pathlib import Path
import hashlib
import json
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parent
BATTLE = ROOT.parent / 'battle-sim-lua'
DECODE = bytes.fromhex(
    '2cf7848bc965fbb69faeb3032d0169741fe4a3ecee5c3421934a0f6ae262029e'
    '229cfd3cfc71c7c6ad596705706d8a4412fa24865fafd17a47cefe5063dd5106'
    '6f18e052a8099d56734cb8536cc3a00e19cf3e0d7e07326846ea48f9992eaba4'
    '49205e5535380cbcd3b1581679280a1ae1f2cdc439dba2ba6072767d95ef7fc8'
    'c0de3794bfb51481922545ace7f566a72b365ac113e34b3ae88d831b7c27b09a'
    '42eb87aadc548e7826d25729d4b7f82f8f8975f04177c21effd81511e5049717'
    'f331d09b00d7cab44f2a3bd9b26bda5da13f3061bd913d4ee6dfbe4d828c1d23'
    '109864f485337b9043bba988f1d6a51cf6cc6eb95b0b96edd5e9c5cb08a68040')
ENCODE = bytes(DECODE.index(i) for i in range(256))
MODULES = {
    'hub': ('Hub', '허브와 캘린더, 캠페인 정비, BattleSim 경기 왕복. /apex로 열기.', '81bc74e7-0b86-42da-a405-4b36177b0e71'),
    'matchmaking': ('Matchmaking', '서사 기반 상대 선정과 고정 컵 일정. Primal Apex 공통 저장 사용.', '81bc74e7-0b86-42da-a405-4b36177b0e72'),
    'story': ('Story', '지도와 NPC 상호작용, LLM 서사, 종료 시각·키워드 정산.', '81bc74e7-0b86-42da-a405-4b36177b0e73'),
    'training': ('Training', 'BattleSim 스킬 습득·레벨 강화. 강화 자원만 소비.', '81bc74e7-0b86-42da-a405-4b36177b0e74'),
}


def decode(raw):
    assert raw[:2] == b'\x6f\x00'
    n = struct.unpack_from('<I', raw, 2)[0]
    return json.loads(raw[6:6+n].translate(DECODE))['module']


def encode(module):
    payload = json.dumps({'type': 'risuModule', 'module': module}, ensure_ascii=False, separators=(',', ':')).encode()
    return b'\x6f\x00' + struct.pack('<I', len(payload)) + payload.translate(ENCODE) + b'\x00'


def lua(v):
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return '{' + ','.join(lua(x) for x in v) + '}'
    return '{' + ','.join('[' + lua(k) + ']=' + lua(x) for k, x in v.items()) + '}'


def skill_metadata(code):
    skills = {}
    for line in code.splitlines():
        m = re.match(r'^\["([a-z0-9_]+)"\]=\{\["schema_version"\]', line)
        if not m:
            continue
        def string_field(name):
            field = re.search(r'\["' + name + r'"\]=("(?:\\.|[^"\\])*")', line)
            assert field, name
            return json.loads(field[1])
        skills[m[1]] = {'name': string_field('name'), 'description': string_field('description'),
                         'maxLevel': int(re.search(r'\["max_level"\]=(\d+)', line)[1])}
    assert len(skills) == 52, f'Unexpected BattleSim skill schema: {len(skills)}'
    for key in ['measured_strike', 'growth_focus', 'banked_pressure']:
        assert skills[key]['maxLevel'] == 3
    return skills


def battle_adapter(code):
    marker = 'if BATTLE_SIM_TEST then return B end'
    assert code.count(marker) == 1
    return '''
-- Unmodified BattleSim engine/UI in a local scope; host hooks are isolated.
local function loadBattle()
  local onStart, onButtonClick
  local function listenEdit() end
  local function reloadDisplay() end
  local function getState(id,key)
    assert(P.battleContext, 'BattleSim requires a campaign transaction')
    if key=='battle_sim_state_v1' then return P.battleContext.battle end
    if key=='battle_sim_config_v2' then return P.battleContext.config end
    error('Unexpected BattleSim storage key: '..key)
  end
  local function setState(id,key,value)
    assert(P.battleContext, 'BattleSim requires a campaign transaction')
    if key=='battle_sim_state_v1' then P.battleContext.battle=value
    elseif key=='battle_sim_config_v2' then P.battleContext.config=value
    else error('Unexpected BattleSim storage key: '..key) end
  end
''' + code.replace(marker, 'return B') + '\nend\nlocal B=loadBattle()\n'


def build():
    release = ROOT / 'release'
    generated = ROOT / 'generated'
    release.mkdir(exist_ok=True)
    generated.mkdir(exist_ok=True)
    source = BATTLE / 'BattleSim-RisuAI.charx'
    with zipfile.ZipFile(source) as z:
        original = decode(z.read('module.risum'))
        scripts = [e['code'] for t in original['trigger'] for e in t['effect'] if e['type'] == 'triggerlua']
        assert len(scripts) == 1
        battle_code = scripts[0]
        card = json.loads(z.read('card.json'))
        battle_css = card['data']['extensions']['risuai']['backgroundHTML']
    skills = skill_metadata(battle_code)
    shared = (ROOT/'src/shared.lua').read_text(encoding='utf-8')
    data = (ROOT/'src/data.lua').read_text(encoding='utf-8')
    runtime = (ROOT/'src/runtime.lua').read_text(encoding='utf-8')
    css = '<style>' + (ROOT/'src/style.css').read_text(encoding='utf-8') + '</style>'
    # Module backgroundEmbedding is raw CSS; chat HTML classes are scoped by RisuAI.
    def scope_css(text):
        return re.sub(r'\.(pa-[\w-]+|bsim-[\w-]+|is-[\w-]+)', r'.x-risu-\1', text)
    manifest = {'version': '0.1.0', 'sharedStateKey': 'primal_apex_state_v1',
                'battleSource': str(source.relative_to(ROOT.parent.parent)),
                'battleLuaSha256': hashlib.sha256(battle_code.encode()).hexdigest(), 'modules': {}}
    for key,(title,description,ident) in MODULES.items():
        code = '-- Primal Apex 0.1.0 / generated by build.py\nlocal PA_MODULE=' + lua(key) + '\n'
        code += shared + '\n' + data + '\nP.skills=' + lua(skills) + '\n'
        if key == 'hub':
            code += battle_adapter(battle_code)
        code += (ROOT/'src'/f'{key}.lua').read_text(encoding='utf-8') + '\n' + runtime
        module = {'name': f'Primal Apex · {title}', 'description': description, 'id': ident,
                  'namespace': f'primal_apex_{key}_v1', 'lowLevelAccess': key in ('hub','story'),
                  'hideIcon': False, 'lorebook': [], 'regex': [], 'assets': [],
                  'backgroundEmbedding': scope_css(css + (battle_css if key == 'hub' else '')),
                  'trigger': [{'comment': f'Primal Apex {title} Lua', 'type': 'manual', 'conditions': [],
                               'effect': [{'type': 'triggerlua', 'code': code, 'indent': 0}],
                               'lowLevelAccess': key in ('hub','story')}]}
        name = f'Primal-Apex-{title}'
        raw = encode(module)
        (release/f'{name}.risum').write_bytes(raw)
        (generated/f'{name}.lua').write_text(code, encoding='utf-8')
        (generated/f'{name}.css').write_text(module['backgroundEmbedding'], encoding='utf-8')
        assert decode(raw) == module
        manifest['modules'][key] = {'file': name+'.risum', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'id': ident}
    assert len(list(release.glob('*.risum'))) == 4
    (release/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
