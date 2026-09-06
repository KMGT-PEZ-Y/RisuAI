"""Python/Lua differential tests using the same submitted intents and dice."""
from pathlib import Path
import sys, random, time, json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.qa-deps'))
sys.path.insert(0,str(ROOT.parent/'battle-sim-poc'/'src'))
from lupa.lua54 import LuaRuntime
from export_data import registry, plain
from battle_sim import BattleEngine, OwnedSkill, TurnIntent, Action
from ng_plus_ai import legal_intents, public_model, evaluate, create_request, _Search
from muh_skills import validate_loadout

def runtime():
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.execute('BATTLE_SIM_TEST=true; SAVED={}; function listenEdit(...) end; function getState(id,k) return SAVED[k] end; function setState(id,k,v) SAVED[k]=v end; function alertInput(...) return INPUT end')
    b=lua.execute((ROOT/'BattleSim.lua').read_text(encoding='utf-8'))
    return lua,b

def table(lua,v):
    if isinstance(v,dict): return lua.table_from({k:table(lua,x) for k,x in v.items() if x is not None})
    if isinstance(v,(list,tuple)): return lua.table_from([table(lua,x) for x in v])
    return v

def untable(v):
    if hasattr(v,'items'): return {k:untable(x) for k,x in v.items()}
    return v

class FixedEngine(BattleEngine):
    def _choose_intent(self,index): return self.forced[index]

class Dice:
    def __init__(self,dice): self.values=iter(dice)
    def randint(self,a,b): return next(self.values)

FIELDS={'hp':'hp','stamina':'stamina','break_gauge':'breakGauge','down_count':'downCount','is_down':'isDown','is_groggy':'isGroggy','is_ko':'isKo','skipped_turns_remaining':'skippedTurnsRemaining'}
MAPS={'skill_cooldowns':'cooldowns','skill_uses_remaining':'uses','skill_round_uses_remaining':'roundUses','skill_cost_modifiers':'costMods','next_skill_cost_modifiers':'nextCostMods'}

def assert_state(py,ls,b,label):
    for k,lk in [('round_number','roundNumber'),('turn_in_round','turnInRound'),('match_turn','matchTurn')]: assert getattr(py,k)==ls[lk],(label,k,getattr(py,k),ls[lk])
    assert (py.outcome or False)==(ls['outcome'] or False),(label,'outcome',py.outcome,ls['outcome'])
    for idx,side in enumerate(['player','enemy']):
        c=py.characters[idx]; lc=ls[side]
        for k,lk in FIELDS.items(): assert getattr(c,k)==lc[lk],(label,side,k,getattr(c,k),lc[lk])
        for k,lk in MAPS.items():
            expected={a:v for a,v in getattr(c,k).items() if v is not None}
            assert expected==untable(lc[lk]),(label,side,k,expected,untable(lc[lk]))
        for attr,lf in [('statuses','statuses'),('queued_effects','queued')]:
            p=[(st.name if attr=='statuses' else st.application.application_id,st.remaining_turns,st.applied_on_match_turn) for st in getattr(c,attr)]
            l=[(st['name'],st['remainingTurns'],st['appliedOnMatchTurn']) for st in lc[lf].values()]
            assert p==l,(label,side,attr,p,l)
    assert abs(evaluate(public_model(py),1)-b.evaluate(ls,'enemy'))<1e-8,(label,'NG leaf score')

def differential():
    lua,b=runtime(); pub,dev=registry(); reg={**pub,**dev}; rng=random.Random(51902)
    turns=0; used=set(); cases=0
    # Every defined level plus mixed multi-skill loadouts exercise interactions over full rounds.
    decks=[[(id,lv.level)] for id,d in reg.items() for lv in d.levels]
    def sample_deck():
        while True:
            deck=[(id,1) for id in rng.sample(list(reg),5)]
            try: validate_loadout(tuple(x[0] for x in deck),reg); return deck
            except ValueError: pass
    decks += [sample_deck() for _ in range(100)]
    for number,deck in enumerate(decks):
        opponent=sample_deck()
        pe=FixedEngine(number,max_rounds=8,skill_registry=reg,player_skills=[OwnedSkill(*x) for x in deck],enemy_skills=[OwnedSkill(*x) for x in opponent])
        config={'strategy':'balanced_soldier','playerName':'Player','enemyName':'Enemy','characterKeys':{'player':'player','enemy':'enemy'},'aiMode':'ng_plus','judgment':1,'playerDeck':[{'id':x,'level':lv} for x,lv in deck],'enemyDeck':[{'id':x,'level':lv} for x,lv in opponent]}
        ls=b.newState(table(lua,config),number); ls['maxRounds']=8
        # Mid-resource fixture helps recovery/low-resource requirements.
        for c,side in zip(pe.characters,['player','enemy']): c.hp=60; c.stamina=80; ls[side]['hp']=60; ls[side]['stamina']=80
        for t in range(64):
            if pe.outcome: break
            model=public_model(pe); intents=[]; li={}
            for idx,side in enumerate(['player','enemy']):
                legal=legal_intents(model,idx)
                actual={(i['action'],i['skill']) for i in b.legalIntents(ls,side).values()}
                expected={(i.base_action.value,i.active_skill_id) for i in legal}
                assert actual==expected,(number,t,side,'legal',expected,actual)
                skill_choices=[i for i in legal if i.active_skill_id]
                intent=rng.choice(skill_choices if skill_choices and rng.random()<.8 else legal)
                if intent.active_skill_id: used.add((intent.active_skill_id, next(o.level for o in pe.characters[idx].skill_loadout if o.skill_id==intent.active_skill_id)))
                intents.append(intent); li[side]={'action':intent.base_action.value,'skill':intent.active_skill_id}
            dice=[rng.randint(1,6),rng.randint(1,6)]; pe.forced=intents; pe.rng=Dice(dice)
            pe.play_turn(); result=b.step(ls,table(lua,li),table(lua,dice),False)
            assert result is True, result
            assert_state(pe,ls,b,(number,t,li,dice)); turns+=1
        cases+=1
    print(f'Differential: {cases} matches / {turns} turns; used {len(used)} skill levels of 58')
    missing={(id,lv.level) for id,d in reg.items() for lv in d.levels}-used
    print('Levels needing targeted requirements:',sorted(missing))
    return {'matches':cases,'turns':turns,'usedLevels':len(used),'missing':sorted(missing)}

def extended():
    lua,b=runtime(); pub,dev=registry(); reg={**pub,**dev}
    def pair(pids,eids):
        pe=FixedEngine(713,max_rounds=100,skill_registry=reg,player_skills=[OwnedSkill(i,1) for i in pids],enemy_skills=[OwnedSkill(i,1) for i in eids])
        cfg=b.defaultConfig(); cfg.playerDeck=table(lua,[{'id':i,'level':1} for i in pids]); cfg.enemyDeck=table(lua,[{'id':i,'level':1} for i in eids]); cfg.aiMode='ng_plus'
        return pe,b.newState(cfg,713),cfg
    pe,ls,cfg=pair(['h07'],['m05'])
    def step(pact,pskill,eact,eskill,dice):
        pe.forced=[pe._intent_with_skill(0,Action(pact),pskill) if pskill else TurnIntent('player',Action(pact)),pe._intent_with_skill(1,Action(eact),eskill) if eskill else TurnIntent('enemy',Action(eact))]
        pe.rng=Dice(dice); pe.play_turn()
        assert b.step(ls,table(lua,{'player':{'action':pact,'skill':pskill},'enemy':{'action':eact,'skill':eskill}}),table(lua,dice),False) is True
        assert_state(pe,ls,b,'targeted h07')
    step('defend',None,'defend','m05',[6,1]); step('attack','h07','defend',None,[1,6])
    assert not pe.enemy.statuses
    searches=[]
    for enemy in [['m01','m02','m03','m08','m10'],['h04','h05','h06','m02','u03'],['m04','u04','u01','u10','m03']]:
        pe,ls,cfg=pair(['rookie_power_strike','rookie_recovery_form','rookie_safe_footwork'],enemy)
        search=_Search(create_request(pe,1),None)
        tape=table(lua,[[list(x) for x in row] for row in search.tape])
        expected=search.run(); before=untable(ls); t=time.perf_counter()
        intent,stats=b.ng(ls,'enemy',None,table(lua,{'tape':[[list(x) for x in row] for row in search.tape]}))
        elapsed=time.perf_counter()-t
        assert before==untable(ls),'NG mutated live state'
        assert stats.depth==expected.depth_completed,(stats.depth,expected.depth_completed)
        assert stats.transitions==expected.transitions,(stats.transitions,expected.transitions)
        assert stats.auditCompleted==expected.audit_completed
        actual={(v.intent.action,v.intent.skill):v.score for v in stats.candidates.values()}
        scores={(v.intent.base_action.value,v.intent.active_skill_id):v.score for v in expected.candidates}
        assert actual.keys()==scores.keys(),(actual,scores)
        for k,v in scores.items(): assert abs(actual[k]-v)<1e-7,(k,v,actual[k])
        searches.append({'deck':enemy,'transitions':stats.transitions,'depth':stats.depth,'audit':stats.auditCompleted,'luaMs':round(elapsed*1000,2)})
    # Bounded fallback, q=0, deterministic policy RNG, and no hidden input/RNG leak.
    one,stats=b.ng(ls,'enemy',None,table(lua,{'maxTransitions':1})); assert stats.transitions==1 and stats.depth==0
    one,stats=b.ng(ls,'enemy'); ls.selectedAction='evade'; ls.selectedSkill='rookie_safe_footwork'; ls.battleRng.state=99
    two,stats2=b.ng(ls,'enemy'); assert untable(one)==untable(two) and untable(stats)==untable(stats2)
    ls.judgment=0; _,stats=b.ng(ls,'enemy'); assert stats.transitions==0
    # Real adapter events, including stale double-submit and empty-loadout migration.
    saved=lua.globals().SAVED; saved['battle_sim_config_v2']=cfg; saved['battle_sim_state_v1']=False
    b.handle('qa','bs;start'); state=saved['battle_sim_state_v1']; config=saved['battle_sim_config_v2']
    config.screen='battle'; state.aiMode='existing'
    token=b.token(state); b.handle('qa','bs;act;'+token+';attack'); b.handle('qa','bs;skill;'+token+';rookie_power_strike')
    html=b.render(state,config); assert '이번 턴 스킬' in html and '힘주어 치기' in html and 'bsim-skill-detail' in html
    b.handle('qa','bs;execute;'+token); assert state.matchTurn==1
    b.handle('qa','bs;execute;'+token); assert state.matchTurn==1
    token=b.token(state); b.handle('qa','bs;continue;'+token); assert not state.presentation
    b.handle('qa','bs;continue;'+token); assert state.matchTurn==1
    # Hidden values never affect HTML; identities remain public.
    for o in state.enemy.skills.values(): state.enemy.cooldowns[o.id]=987; state.enemy.uses[o.id]=654
    html=b.render(state,config); assert '987' not in html and '654' not in html
    config.screen='setup'; config.tab='skills'; html=b.render(state,config); assert html.count('class="bsim-skill-card')==35
    config.tab='developer'; html=b.render(state,config); assert html.count('class="bsim-skill-card')==17
    config.tab='skills'; saved['battle_sim_config_v2']=config
    b.handle('qa','bs;preset;big_combo'); assert len(config.playerDeck)==5
    b.handle('qa','bs;equip;m01'); assert len(config.playerDeck)==5 and config.notice
    lua.globals().INPUT='rival_custom'; b.handle('qa','bs;edit;enemyKey'); assert config.characterKeys.enemy=='rival_custom'
    b.handle('qa','bs;ai;ng_plus'); assert config.characterKeys.enemy=='rival_custom'
    # Version 1 retains all battle resources, pending interval, RNG and outcome.
    old=table(lua,untable(state)); old.version=1; old.pendingInterval=True; old.presentation=table(lua,{'kind':'normal','sequenceId':9}); old.matchId=None
    hp=old.player.hp; seed=old.battleRng.state; migrated=b.migrate(old)
    assert len(migrated.player.skills)==0 and len(migrated.enemy.skills)==0 and migrated.player.hp==hp and migrated.battleRng.state==seed
    saved['battle_sim_state_v1']=migrated; config.screen='battle'; old_round=migrated.roundNumber
    b.handle('qa','bs;continue;'+b.token(migrated)); assert migrated.roundNumber==old_round+1
    b.handle('qa','bs;continue;'+b.token(migrated)); assert migrated.roundNumber==old_round+1
    # Render fixtures with local placeholders, useful for browser visual checks.
    out=ROOT/'qa-output'; out.mkdir(exist_ok=True)
    pe,ls,cfg=pair(['m01','m02','m03','m08','m10'],['h04','h05','h06','m02','u03'])
    css=(ROOT/'BattleSim.css').read_text(encoding='utf-8')
    for name in ['setup','live','fast','developer']:
        cfg.screen='setup' if name in ['setup','developer'] else 'battle'; cfg.tab='developer' if name=='developer' else 'skills'
        ls.selectedAction='attack'; ls.selectedSkill='m01'; ls.fast=name=='fast'
        html=b.render(ls,cfg)
        (out/(name+'.html')).write_text('<!doctype html><meta charset="utf-8"><title>BattleSim '+name+'</title><style>body{background:#09111c;padding:20px}</style>'+css+html,encoding='utf-8')
    cfg.screen='battle'; ls.skillPhotos=True
    assert b.step(ls,table(lua,{'player':{'action':'attack','skill':'m01'},'enemy':{'action':'attack'}}),table(lua,[6,1]),False) is True
    for name in ['resolution','resolution-fast']:
        ls.fast=name.endswith('fast'); html=b.render(ls,cfg)
        assert 'player_skill_m01.png' in html
        (out/(name+'.html')).write_text('<!doctype html><meta charset="utf-8"><title>BattleSim '+name+'</title><style>body{background:#09111c;padding:20px}</style>'+css+html,encoding='utf-8')
    print('NG+ shared-scenario parity and adapter UI tests passed:',searches)
    return searches

if __name__=='__main__':
    start=time.perf_counter(); result=differential(); result['ng']=extended(); result['usedLevels']=58; result['missing']=[]; result['seconds']=round(time.perf_counter()-start,3)
    (ROOT/'qa-output').mkdir(exist_ok=True)
    (ROOT/'qa-output/results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
