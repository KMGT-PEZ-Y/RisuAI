-- Small editable campaign data. BattleSim skill metadata is inserted by build.py.
P.growthSkills={'measured_strike','growth_focus','banked_pressure'}
P.npcs={
  {id='rookie_cycle',name='훈련생',place='gym',aiMode='existing',strategy='rookie_cycle',adult=true,
    bio='기본기를 연습하며 첫 리그 경기를 준비하는 성인 선수. 솔직하고 배우려는 의지가 강하다.',
    deck={{id='rookie_power_strike',level=1},{id='rookie_recovery_form',level=1},{id='rookie_safe_footwork',level=1}}},
  {id='veteran_guard',name='베테랑 가드',place='cafe',aiMode='existing',strategy='veteran_guard',adult=true,
    bio='수비와 꾸준한 훈련을 중시하는 성인 선수. 상대의 경기 태도와 약속을 중요하게 여긴다.',
    deck={{id='rookie_tuck_chin',level=1},{id='rookie_recovery_form',level=1}}},
  {id='adaptive',name='적응형 전사',place='arena',aiMode='ng_plus',strategy='adaptive',adult=true,
    bio='새로운 전술과 경쟁을 즐기는 성인 선수. 상대의 발전을 확인하기 위해 대결을 제안한다.',
    deck={{id='rookie_power_strike',level=1},{id='rookie_safe_footwork',level=1}}},
}
P.places={{id='gym',name='체육관',description='선수들과 기본기와 다음 경기를 이야기합니다.'},
  {id='cafe',name='카페',description='경기장 밖에서 편하게 대화합니다.'},
  {id='arena',name='아레나',description='경기와 라이벌에 관한 소식을 듣습니다.'}}
P.interactions={{id='TALK',name='대화하기'},{id='HELP',name='부탁과 작은 퀘스트'},{id='CHALLENGE',name='대전 이야기'}}
function P.npc(id) for _,n in ipairs(P.npcs) do if n.id==id then return n end end end
function P.place(id) for _,p in ipairs(P.places) do if p.id==id then return p end end end
