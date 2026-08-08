/* overlay.h -- on-screen FPS counter drawn in the eglSwapBuffers hook
 *
 * This software may be modified and distributed under the terms
 * of the MIT license. See the LICENSE file for details.
 */

#ifndef __OVERLAY_H__
#define __OVERLAY_H__

// eglSwapBuffers replacement for the import table: draws the FPS counter
// (config.show_fps) over the game's output before presenting.
unsigned int eglSwapBuffersHook(void *display, void *surface);

#endif
