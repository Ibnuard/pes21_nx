"""Release builds retain bounded native errors without enabling verbose logs."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

SOURCE = (Path(__file__).resolve().parents[1]/'source/imports.c').read_text()


class NativeErrorJournalTests(unittest.TestCase):
    def test_release_filter_format_and_independent_fatal_budget(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        helpers = ''.join(function(SOURCE, n) for n in (
            'native_error_note', 'android_log_message', '__android_log_print',
            '__android_log_write', '__android_log_vprint'))
        build_and_run(gcc, r'''
#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
static int errors,fatals;
static char last[1152];
static void scene_runtime_note(const char *area,const char *message) {
  if(!strcmp(area,"native fatal"))++fatals;else ++errors;
  assert(strlen(message)<sizeof(last));strcpy(last,message);
}
''' + helpers + r'''
static int via_list(int priority,const char *fmt,...) {
  va_list args;va_start(args,fmt);
  int result=__android_log_vprint(priority,"UE4",fmt,args);
  va_end(args);return result;
}
int main(void) {
  int untouched=-1;
  assert(!__android_log_print(4,"UE4","quiet%n",&untouched));
  assert(untouched==-1&&!errors&&!fatals);
  assert(!via_list(6,"shader=%d %s",23,"failed"));
  assert(errors==1&&!strcmp(last,"UE4: shader=23 failed"));
  assert(!__android_log_print(6,NULL,"allocation %u",4u));
  assert(errors==2&&!strcmp(last,": allocation 4"));
  char large[4096];memset(large,'x',sizeof(large));large[4095]=0;
  assert(!__android_log_write(6,"UE4",large));
  assert(errors==3&&strlen(last)==1029);
  for(int i=0;i<30;++i)__android_log_write(6,"UE4","repeated error");
  assert(errors==8&&!fatals);
  // Earlier nonfatal errors must not consume the later fatal-error allowance.
  assert(!__android_log_print(7,"UE4","missing %s","material"));
  assert(fatals==1&&!strcmp(last,"UE4: missing material"));
  assert(!via_list(7,NULL));assert(fatals==2&&!strcmp(last,"UE4: "));
  for(int i=0;i<30;++i)__android_log_write(7,NULL,NULL);
  assert(fatals==8&&errors==8);
}
''')
