    .text
    .align 2
    .global cobra_pad_update_hook
    .type cobra_pad_update_hook, %function

// Mid-function hook for cobra::game::Pad::Update + 0xd4. x19 is the Pad
// instance here. The surrounding function has no live caller-saved values
// after this point; preserve its frame/link registers, inject the current
// Switch state, replay the four overwritten instructions, then resume at +0xe4.
cobra_pad_update_hook:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    mov x0, x19
    bl cobra_pad_apply_input
    mov x17, x0
    ldp x29, x30, [sp], #16

    ldp w11, w9, [x19, #12]
    mov x8, xzr
    add x10, x19, #0x20
    bic w12, w9, w11

    br x17

    .size cobra_pad_update_hook, .-cobra_pad_update_hook

    .align 2
    .global pes_mobile_screen_tap_entry_hook
    .type pes_mobile_screen_tap_entry_hook, %function

// Entry hook for ScreenTapManager::Update. Preserve every integer argument and
// the caller frame, publish mode from the original ControlModeInfo* in x2,
// replay the four overwritten prologue instructions, and resume at +0x10.
pes_mobile_screen_tap_entry_hook:
    sub sp, sp, #0x50
    stp x0, x1, [sp, #0x00]
    stp x2, x3, [sp, #0x10]
    stp x4, x5, [sp, #0x20]
    stp x6, x7, [sp, #0x30]
    stp x29, x30, [sp, #0x40]
    ldr x0, [sp, #0x10]
    bl pes_mobile_screen_tap_entry
    mov x17, x0
    ldp x29, x30, [sp, #0x40]
    ldp x6, x7, [sp, #0x30]
    ldp x4, x5, [sp, #0x20]
    ldp x2, x3, [sp, #0x10]
    ldp x0, x1, [sp, #0x00]
    add sp, sp, #0x50

    sub sp, sp, #0x190
    stp d15, d14, [sp, #0xf0]
    stp d13, d12, [sp, #0x100]
    stp d11, d10, [sp, #0x110]
    br x17

    .size pes_mobile_screen_tap_entry_hook, .-pes_mobile_screen_tap_entry_hook
