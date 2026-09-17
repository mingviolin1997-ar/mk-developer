import unittest
from check_reader_sources import check
class CheckTests(unittest.TestCase):
 def test_failure_preserves_last_success_and_never_calls_it_current(self):
  old={'lastSuccess':{'version':'1.2','checkedAt':'yesterday'}}
  def fail(url): raise OSError('offline')
  result=check({'id':'a','name':'a','mode':'version-api','urls':['https://example.org']},old,fail,'today')
  self.assertEqual(result['status'],'failed');self.assertEqual(result['lastSuccess'],old['lastSuccess'])
 def test_invalid_payload_never_promoted(self):
  result=check({'id':'a','name':'a','mode':'monitor-only','urls':['https://example.org']},{},lambda _:b'{"error":"no"}')
  self.assertEqual(result['status'],'failed');self.assertNotIn('lastSuccess',result)
 def test_version_is_not_derived_from_check_time(self):
  result=check({'id':'a','name':'a','mode':'version-api','urls':['https://example.org']},{},lambda _:b'{"version3":"5.9.5","update_log":{}}','today')
  self.assertEqual(result['lastSuccess']['version'],'5.9.5');self.assertEqual(result['status'],'checked')
if __name__=='__main__': unittest.main()
