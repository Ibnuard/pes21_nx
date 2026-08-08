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
