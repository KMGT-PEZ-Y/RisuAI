"""Package Lua/CSS into CHARX without extracting or deleting directories."""
from pathlib import Path
import argparse, json, re, struct, zipfile, hashlib
from datetime import datetime, timezone
from assemble import assemble

ROOT=Path(__file__).resolve().parent

def codec():
    script=(ROOT/'build.ps1').read_text(encoding='utf-8-sig')
    block=re.search(r'\$decodeMapHex\s*=\s*@\((.*?)\)\s*-join',script,re.S).group(1)
    decode=bytes.fromhex(''.join(re.findall(r"'([0-9a-f]+)'",block)))
    assert len(decode)==256 and len(set(decode))==256
    encode=bytes(decode.index(i) for i in range(256))
    return decode,encode

def decode_module(raw):
    decode,_=codec(); length=struct.unpack_from('<I',raw,2)[0]
    assert raw[:2]==bytes([111,0]) and len(raw)>=6+length
    return json.loads(raw[6:6+length].translate(decode))

def encode_module(data):
    _,encode=codec(); raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return bytes([111,0])+struct.pack('<I',len(raw))+raw.translate(encode)+b'\0'

def build(source,output):
    assemble()
    with zipfile.ZipFile(source) as z: entries={name:z.read(name) for name in z.namelist()}
    module=decode_module(entries['module.risum'])
    effects=[e for t in module['module']['trigger'] for e in t['effect'] if e['type']=='triggerlua']
    assert len(effects)==1,'Expected one existing Lua trigger'
    lua=(ROOT/'BattleSim.lua').read_text(encoding='utf-8'); css=(ROOT/'BattleSim.css').read_text(encoding='utf-8')
    effects[0]['code']=lua
    module['module']['description']='Python POC 스킬 52종, 기존 AI·NG+, 캐릭터·덱 설정을 이식한 Lua 전투 모듈'
    entries['module.risum']=encode_module(module)
    card=json.loads(entries['card.json']); data=card['data']
    data['description']='35종 공개 스킬과 개발자 테스트 17종, NG+ AI, 자유 장착·프리셋, 캐릭터별 사진과 빠른 진행을 지원하는 RisuAI Lua POC입니다.'
    data['first_mes']='대전 준비 패널에서 캐릭터, AI, 덱을 선택하세요. 진행 중에도 대전 설정으로 돌아갈 수 있습니다. `/battle`로 설정 패널을 다시 열 수 있습니다.'
    data['character_version']='2.0.0'
    data['modification_date']=int(datetime.now(timezone.utc).timestamp())
    data['extensions']['risuai']['backgroundHTML']=css
    entries['card.json']=json.dumps(card,ensure_ascii=False,indent=2).encode('utf-8')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in entries.items(): z.writestr(name,content)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        m=decode_module(z.read('module.risum')); c=json.loads(z.read('card.json'))
        embedded=[e['code'] for t in m['module']['trigger'] for e in t['effect'] if e['type']=='triggerlua']
        assert embedded==[lua]
        assert c['data']['extensions']['risuai']['backgroundHTML']==css
    print(f'Built and verified: {output.name} ({output.stat().st_size:,} bytes)')
    print('SHA256:',hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT/'BattleSim-RisuAI.before-skills.charx')
    parser.add_argument('--output',type=Path,default=ROOT/'BattleSim-RisuAI.charx')
    args=parser.parse_args(); build(args.source,args.output)
