"use strict";
(() => {
const status=document.getElementById("status"),open=document.getElementById("open");
function render() {
open.hidden=true;open.removeAttribute("href");
try {
 const payload=location.hash.slice(1);
 if(payload.length>6000 || !/^[A-Za-z0-9_-]+$/.test(payload)) throw Error();
 const bytes=Uint8Array.from(atob(payload.replace(/-/g,"+").replace(/_/g,"/")),c=>c.charCodeAt(0));
 const data=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));
 const keys=["version","title","author","sourceHost","layout","platform","bookKey"];
 if(!data || Array.isArray(data) || Object.keys(data).some(k=>!keys.includes(k)) || data.version!==1 || typeof data.bookKey!=="string" || !/^[a-f0-9]{64}$/.test(data.bookKey) || typeof data.title!=="string" || !data.title || data.title.length>900) throw Error();
 document.getElementById("title").textContent=data.title;
 open.href="accessreader://book?data="+encodeURIComponent(payload);open.hidden=false;
 status.textContent="点击下方按钮打开书籍。";
} catch {status.textContent="分享链接无效，请让朋友重新分享。";}
}
render();addEventListener("hashchange",render);
})();
