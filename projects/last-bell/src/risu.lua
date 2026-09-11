local function load(id)
  local ok,s=pcall(getState,id,G.key)
  if not ok or type(s)~='table' then return G.new() end
  if s.version~=G.version then return nil end
  return s
end
function G.handle(id,code)
  if type(code)~='string' then return end
  local serial,rev,action,value=code:match('^lb;(%d+);(%d+);([%a]+);([%w_]*)$')
  if not action then return end
  local s=load(id)
  if not s or s.serial~=tonumber(serial) or s.revision~=tonumber(rev) then return end
  if G.reduce(s,action,value) then
    s.revision=s.revision+1
    setState(id,G.key,s)
    if reloadDisplay then reloadDisplay(id) end
  end
end
listenEdit('editDisplay',function(id,data,meta)
  if meta and meta.index~=nil and meta.index~=getChatLength(id)-1 then return data end
  local s=load(id)
  if not s then return data..'\n\n<div>LAST BELL: 더 새로운 버전의 저장입니다. 최신 모듈을 사용하세요.</div>' end
  return data..'\n\n'..G.render(s)
end)
onButtonClick=async and async(G.handle) or G.handle
onStart=function(id)
  local chat=getFullChat(id); local last=chat[#chat]
  if not last or last.role~='user' then return end
  local cmd=last.data:match('^%s*(.-)%s*$')
  if cmd~='/boxing' and cmd~='/lastbell' then return end
  removeChat(id,getChatLength(id)-1)
  addChat(id,'char','LAST BELL · 링 사이드에 오신 것을 환영합니다.')
  stopChat(id)
end
if LAST_BELL_TEST then LAST_BELL=G end
