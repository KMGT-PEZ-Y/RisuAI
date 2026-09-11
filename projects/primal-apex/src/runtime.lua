-- The host dispatches a button to every enabled module. Only its owner acts.
local function buttonHandler(id,code)
  if type(code)~='string' then return end
  local owner,rev,action,value=code:match('^pa;([a-z]+);(%d+);([a-z_]+);(.*)$')
  if owner~=P.module then return end
  local s,why=P.load(id); if not s then P.notice(id,why); return end
  if s.revision~=tonumber(rev) then P.notice(id,'오래된 버튼입니다. 현재 화면에서 다시 선택해 주세요.'); P.refresh(id); return end
  if not M.owns(s) then return end
  local expected=s.revision; s=P.copy(s); s.notice=nil
  local safe,ok,msg,effect=pcall(M.handle,id,s,action,value)
  if not safe then P.notice(id,'처리에 실패했습니다. 기존 상태는 보존됩니다.'); if log then log(tostring(ok)) end; return end
  if not ok then if msg then P.notice(id,msg) end; return end
  local committed,err=P.commit(id,s,expected)
  if not committed then P.notice(id,err); return end
  if effect then effect(id) end
  P.refresh(id)
end
onButtonClick=async and async(buttonHandler) or buttonHandler
listenEdit('editDisplay',function(id,data,meta)
  data=P.strip(data)
  if meta and meta.index~=nil and meta.index~=getChatLength(id)-1 then return data end
  local s,why=P.load(id)
  if not s then return P.module=='hub' and data..'<p class="pa-notice">'..P.esc(why)..'</p>' or data end
  if not M.owns(s) then return data end
  return data..P.scope(M.render(s))
end)
if not M.owns then M.owns=function(s) return s.screen==P.module end end
if M.start then onStart=async and async(M.start) or M.start end
if M.output then onOutput=async and async(M.output) or M.output end
if M.request then listenEdit('editRequest',M.request) end
if PRIMAL_APEX_TEST then PA_TEST={P=P,M=M} end
