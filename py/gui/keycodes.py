KEYCODES = {'Escape'    : 9,
            'Arrow_down': 116,
            'Arrow_up'  : 111,
            'A'         : 38,
            'J'         : 44,
            'K'         : 45,
            'R'         : 27,
            'L'         : 46,
            'W'         : 25,
            'C'         : 54,
            'D'         : 40,
            'H'         : 43,
            'Backslash' : 22,
            'Backspace' : 51,
            'Space'     : 65,
            'Hypen'     : 20,
            'Equals'      : 21,
            'Hyphen'    : 20,
            'N'   : 57
           }


KEYCODE_TO_CHR = {value: key for (key, value) in KEYCODES.iteritems()}


def parse_keycode_to_textual_repr(keycode, is_ctrl_pressed, is_shift_pressed):
    keycode_text_repr = ""
    if is_ctrl_pressed:
        keycode_text_repr += "Ctrl+"
    if is_shift_pressed:
        keycode_text_repr += "Shift+"
    keycode_text_repr += KEYCODE_TO_CHR.get(keycode, "UNKNOWN")
    return keycode_text_repr
