KEYCODES = {'Escape'    : 9,
            'Arrow_down': 116,
            'Arrow_up'  : 111,
            'Two'       : 11,
            'Four'      : 13,
            'Five'      : 14,
            'A'         : 38,
            'C'         : 54,
            'D'         : 40,
            'H'         : 43,
            'I'         : 31,
            'J'         : 44,
            'K'         : 45,
            'L'         : 46,
            'M'         : 58,
            'R'         : 27,
            'W'         : 25,
            'Backslash' : 22,
            'Backspace' : 51,
            'Space'     : 65,
            'Hyphen'    : 20,
            'Equals'    : 21,
            'N'         : 57
           }


KEYCODE_TO_CHR = {value: key for (key, value) in KEYCODES.iteritems()}


def parse_keycode_to_textual_repr(keycode, is_ctrl_pressed, is_shift_pressed):
    keycode_text_repr = ""
    if is_ctrl_pressed:
        keycode_text_repr += "Ctrl_"
    if is_shift_pressed:
        keycode_text_repr += "Shift_"
    keycode_text_repr += KEYCODE_TO_CHR.get(keycode, "UNKNOWN")
    return keycode_text_repr
