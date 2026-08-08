/* jni_fake.h -- fake JNI environment for the GTA:SA oswrapper/GameNative layer
 *
 * The game reaches a thin Java platform layer over JNI for a few things (the
 * app-local key/value store, splash screen, device locale/version).
 * We emulate just enough JavaVM/JNIEnv for those calls to resolve; all bulk data
 * is loaded natively, not through Java.
 *
 * This software may be modified and distributed under the terms
 * of the MIT license. See the LICENSE file for details.
 */

#ifndef __JNI_FAKE_H__
#define __JNI_FAKE_H__

#include <stdint.h>

// passed to JNI_OnLoad and to every JNI entry point as (JNIEnv*, jobject, ...)
extern void *fake_vm;  // JavaVM *
extern void *fake_env; // JNIEnv *

// set when the game asks to quit
extern volatile int jni_quit_requested;

// set once the engine reports the loading splash should hide
extern volatile int jni_frontend_ready;

void jni_init(void);
void jni_set_native_init_hmds(void (*callback)(void *env, void *activity));

// ---------------------------------------------------------------------------
// deferred native callbacks: GameNative entry points the Java platform layer
// would fire back asynchronously. The engine blocks in early boot states until
// these complete; we queue them from the JNI dispatch and the main loop invokes
// the matching impl* entry point.
// ---------------------------------------------------------------------------

typedef enum {
  JNI_CB_PLAYLIST_OPEN_COMPLETE = 1, // implOnPlaylistOpenComplete(success, count)
  JNI_CB_ROCKSTAR_INITIAL_COMPLETE,  // implOnRockstarInitialComplete()
  JNI_CB_ROCKSTAR_GATE_COMPLETE,     // implOnRockstarGateComplete(gate, success)
  JNI_CB_ROCKSTAR_SIGNIN_COMPLETE,   // implOnRockstarSignInComplete()
  JNI_CB_ROCKSTAR_SIGNOUT_COMPLETE,  // implOnRockstarSignOutComplete()
} JniCallbackType;

typedef struct {
  JniCallbackType type;
  int arg0, arg1;
} JniCallback;

// returns 0 when the queue is empty
int jni_pop_callback(JniCallback *out);

// constructors for fake Java objects to pass into the game's JNI entry points
void *jni_make_string(const char *utf);
void *jni_make_string_array(int n, const char **strs);
void *jni_make_int_array(int n, const int *vals);
void *jni_make_object(const char *label);

#endif
