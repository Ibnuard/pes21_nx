"""UE4.22 Win64 editor-only reflection bridge for non-Python Cascade classes.

Uses exported UObject construction/property APIs from the installed editor.
No fixed object offsets, game DLL modification, or runtime plugin is involved.
Run only inside the UE4.22 Python commandlet, on newly authored local assets.
"""
import ctypes as C
import unreal

if not unreal.SystemLibrary.get_engine_version().startswith('4.22.'):
    raise RuntimeError('This asset authoring bridge requires UE4.22')

P = C.c_void_p
core = C.CDLL('UE4Editor-CoreUObject.dll')


def bind(dll, name, result, args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args
    return fn


class Name(C.Structure):
    _fields_ = [('comparison', C.c_uint32), ('display', C.c_uint32), ('number', C.c_uint32)]


class String(C.Structure):
    _fields_ = [('data', P), ('num', C.c_int32), ('max', C.c_int32)]


find = bind(core, '?StaticFindObject@@YAPEAVUObject@@PEAVUClass@@PEAV1@PEB_W_N@Z',
            P, [P, P, C.c_wchar_p, C.c_bool])
construct = bind(core, '?StaticConstructObject_Internal@@YAPEAVUObject@@PEAVUClass@@PEAV1@VFName@@W4EObjectFlags@@W4EInternalObjectFlags@@1_NPEAUFObjectInstancingGraph@@5@Z',
                 P, [P, P, Name, C.c_uint32, C.c_uint32, P, C.c_bool, P, C.c_bool])
offset = bind(core, '?GetOffset_ForInternal@UProperty@@QEBAHXZ', C.c_int32, [P])
import_text = bind(core, '?ImportText@UProperty@@QEBAPEB_WPEB_WPEAXHPEAVUObject@@PEAVFOutputDevice@@@Z',
                   P, [P, C.c_wchar_p, P, C.c_int32, P, P])
get_path = bind(core, '?GetPathName@UObjectBaseUtility@@IEBAXPEBVUObject@@AEAVFString@@@Z',
                None, [P, P, C.POINTER(String)])
post_edit = bind(core, '?PostEditChange@UObject@@QEAAXXZ', None, [P])
free = bind(C.CDLL('UE4Editor-Core.dll'), '?Free@FMemory@@SAXPEAX@Z', None, [P])


def object_ptr(obj):
    result = find(None, None, obj.get_path_name(), False)
    if not result:
        raise RuntimeError('Object unavailable: ' + obj.get_path_name())
    return result


def object_path(ptr):
    result = String()
    get_path(ptr, None, C.byref(result))
    try:
        if not result.data or not 0 < result.num < 2048:
            raise RuntimeError('Invalid editor object path')
        return C.wstring_at(result.data)
    finally:
        if result.data:
            free(result.data)


def new(kind, outer):
    cls = find(None, None, '/Script/Engine.' + kind, False)
    if not cls:
        # Loading the class also registers its native default object/properties.
        unreal.load_class(None, '/Script/Engine.' + kind)
        cls = find(None, None, '/Script/Engine.' + kind, False)
    if not cls:
        raise RuntimeError('Unknown engine class: ' + kind)
    result = construct(cls, outer, Name(), 8, 0, None, False, None, False)
    if not result:
        raise RuntimeError('Cannot construct ' + kind)
    return result


def set_value(obj, owner, field, value):
    cls = find(None, None, '/Script/Engine.' + owner, False)
    prop = find(None, cls, field, False) if cls else None
    if not prop:
        raise RuntimeError('Unknown property: ' + owner + '.' + field)
    field_offset = offset(prop)
    if not 0 <= field_offset < 65536:
        raise RuntimeError('Invalid property offset')
    if not import_text(prop, str(value), obj + field_offset, 0, obj, None):
        raise RuntimeError('Cannot import ' + owner + '.' + field + '=' + str(value))


def ref(obj):
    return '"' + object_path(obj) + '"'


def refs(objects):
    return '(' + ','.join(ref(x) for x in objects) + ')'
