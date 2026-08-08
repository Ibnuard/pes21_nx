    .text
    .align 2
    .global ue4_object_initializer_resize_hook
    .type ue4_object_initializer_resize_hook, %function

// The crashing StaticConstructObject_Internal caller keeps OldNum in x19 and
// uses it immediately after ResizeGrow. Preserve normal ABI behavior, but when
// x19 matches the corrupt argument, replace it with the sanitized index returned
// by the C handler.
ue4_object_initializer_resize_hook:
    sub sp, sp, #48
    stp x29, x30, [sp]
    stp x20, x21, [sp, #16]
    str x19, [sp, #32]
    mov x29, sp
    mov x20, x19
    mov x21, x1
    bl ue4_object_initializer_resize_hook_c
    cmp x20, x21
    b.ne 1f
    mov w19, w0
    b 2f
1:
    mov x19, x20
2:
    ldp x20, x21, [sp, #16]
    ldp x29, x30, [sp]
    add sp, sp, #48
    ret

    .size ue4_object_initializer_resize_hook, .-ue4_object_initializer_resize_hook
