/* VAOs are context-local containers. Never edit the engine's currently bound
 * container: its RHI can legitimately reuse that layout without resubmitting
 * attribute pointers, integer formats, divisors or the element-buffer bind. */
#ifndef GL_VERTEX_ARRAY_BINDING
#define GL_VERTEX_ARRAY_BINDING 0x85b5
#endif
#ifndef GL_DRAW_FRAMEBUFFER
#define GL_DRAW_FRAMEBUFFER 0x8ca9
#endif
#ifndef GL_READ_FRAMEBUFFER
#define GL_READ_FRAMEBUFFER 0x8ca8
#define GL_READ_FRAMEBUFFER_BINDING 0x8caa
#endif
typedef void (*OverlayGenVertexArraysProc)(GLsizei, GLuint *);
typedef void (*OverlayBindVertexArrayProc)(GLuint);
static OverlayGenVertexArraysProc overlay_gen_vertex_arrays;
static OverlayBindVertexArrayProc overlay_bind_vertex_array;
static Mutex overlay_vertex_mutex;
static struct { EGLContext context; GLuint vao; } overlay_vertex_contexts[32];

static int overlay_vertex_begin(GLuint buffer, GLuint position, GLuint uv,
                                GLint *previous) {
  const EGLContext context = eglGetCurrentContext();
  if (context == EGL_NO_CONTEXT) return 0;
  mutexLock(&overlay_vertex_mutex);
  if (!overlay_gen_vertex_arrays || !overlay_bind_vertex_array) {
    overlay_gen_vertex_arrays =
        (OverlayGenVertexArraysProc)eglGetProcAddress("glGenVertexArrays");
    overlay_bind_vertex_array =
        (OverlayBindVertexArrayProc)eglGetProcAddress("glBindVertexArray");
    if (!overlay_gen_vertex_arrays || !overlay_bind_vertex_array) {
      overlay_gen_vertex_arrays =
          (OverlayGenVertexArraysProc)eglGetProcAddress("glGenVertexArraysOES");
      overlay_bind_vertex_array =
          (OverlayBindVertexArrayProc)eglGetProcAddress("glBindVertexArrayOES");
    }
  }
  int slot = -1, empty = -1;
  for (unsigned i = 0; i < 32; ++i) {
    if (overlay_vertex_contexts[i].context == context) { slot = (int)i; break; }
    if (!overlay_vertex_contexts[i].context && empty < 0) empty = (int)i;
  }
  if (slot < 0) slot = empty;
  if (slot < 0 || !overlay_gen_vertex_arrays || !overlay_bind_vertex_array) {
    mutexUnlock(&overlay_vertex_mutex);
    return 0; /* Fail without modifying the engine's vertex state. */
  }
  glGetIntegerv(GL_VERTEX_ARRAY_BINDING, previous);
  if (!overlay_vertex_contexts[slot].vao) {
    GLuint vao = 0;
    overlay_gen_vertex_arrays(1, &vao);
    if (!vao) { mutexUnlock(&overlay_vertex_mutex); return 0; }
    GLint previous_buffer;
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &previous_buffer);
    overlay_bind_vertex_array(vao);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glEnableVertexAttribArray(position);
    glEnableVertexAttribArray(uv);
    glVertexAttribPointer(position, 2, GL_FLOAT, GL_FALSE, 16, (const void *)0);
    glVertexAttribPointer(uv, 2, GL_FLOAT, GL_FALSE, 16, (const void *)8);
    glBindBuffer(GL_ARRAY_BUFFER, (GLuint)previous_buffer);
    overlay_vertex_contexts[slot].vao = vao;
    overlay_vertex_contexts[slot].context = context;
  } else {
    overlay_bind_vertex_array(overlay_vertex_contexts[slot].vao);
  }
  mutexUnlock(&overlay_vertex_mutex);
  return 1;
}

static void overlay_vertex_end(GLint previous) {
  overlay_bind_vertex_array((GLuint)previous);
}

void overlay_context_destroyed(void *context) {
  /* EGL owns the object destruction. The destroying thread need not be the
   * render thread; remove the key so a recycled EGL handle gets a fresh VAO. */
  mutexLock(&overlay_vertex_mutex);
  for (unsigned i = 0; i < 32; ++i)
    if (overlay_vertex_contexts[i].context == (EGLContext)context) {
      overlay_vertex_contexts[i].context = EGL_NO_CONTEXT;
      overlay_vertex_contexts[i].vao = 0;
    }
  mutexUnlock(&overlay_vertex_mutex);
}
