const notice = document.querySelector('#notice');
document.querySelector('#registration').addEventListener('submit', event => {
  event.preventDefault();
  const name = document.querySelector('#nickname').value.trim();
  const udid = document.querySelector('#udid').value.trim().toUpperCase();
  if (!name || !/^(?:[A-F0-9]{8}-[A-F0-9]{16}|[A-F0-9]{40})$/.test(udid)) {
    notice.textContent = '请填写昵称，并粘贴完整的 iPhone UDID。请勿填写序列号或 IMEI。';
    document.querySelector('#udid').focus();
    return;
  }
  document.querySelector('#message').value = `申请测试：听弦、小铭读书\n昵称：${name}\niPhone UDID：${udid}`;
  document.querySelector('#result').hidden = false;
  notice.textContent = '信息已生成，还没有发送。请复制后发给小铭。';
  document.querySelector('#message').focus();
});
document.querySelector('#copy').addEventListener('click', async () => {
  const field = document.querySelector('#message');
  try {
    await navigator.clipboard.writeText(field.value);
    notice.textContent = '已复制，请到聊天中粘贴并发送给小铭。';
  } catch {
    field.focus(); field.select();
    notice.textContent = '请手动复制上面的登记信息，再发给小铭。';
  }
});
// Installation links are explicit per friend in HTML. Never replace them
// from a shared latest-release feed: that could point another friend at the wrong package.
