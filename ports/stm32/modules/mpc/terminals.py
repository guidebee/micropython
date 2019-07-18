from uio import IOBase
from pyb import UART
from mpc.lcd import *
from mpc import Screen, Stream
from ucollections import deque
import time
import gc

hid_key_code = [None, 'ERR_OVF', None, None, 'A', 'B', 'C', 'D', 'E', 'F',
                'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q',
                'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '1', '2',
                '3', '4', '5', '6', '7', '8', '9', '0', 'ENTER', 'ESC',
                'BACKSPACE', 'TAB', 'SPACE', 'MINUS', 'EQUAL', 'LEFT_BRACE', 'RIGHT_BRACE',
                'BACKSLASH', 'HASH_TILDE', 'SEMICOLON', 'APOSTROPHE', 'GRAVE', 'COMMA',
                'PERIOD', 'FORWARD_SLASH', 'CAPS_LOCK', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6',
                'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'PRINT_SCREEN', 'SCROLL_LOCK',
                'PAUSE', 'INSERT', 'HOME', 'PAGE_UP', 'DELETE', 'END', 'PAGE_DOWN',
                'RIGHT_ARROW', 'LEFT_ARROW', 'DOWN_ARROW', 'UP_ARROW', 'NUM_LOCK', 'KP_SLASH', 'KP_ASTERISK',
                'KP_MINUS', 'KP_PLUS', 'KP_ENTER', 'KP1', 'KP2', 'KP3', 'KP4', 'KP5',
                'KP6', 'KP7', 'KP8', 'KP9', 'KP0', 'KP_PERIOD', '102ND', 'COMPOSE',
                'POWER', 'KP_EQUAL', 'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19',
                'F20', 'F21', 'F22', 'F23', 'F24', 'OPEN', 'HELP', 'PROPS', 'FRONT',
                'STOP', 'AGAIN', 'UNDO', 'CUT', 'COPY', 'PASTE', 'FIND', 'MUTE']

key_code_ascii = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f',
                  'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l',
                  'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p',
                  'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v',
                  'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z',
                  '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
                  '7': '7', '8': '8', '9': '9', '0': '0',
                  'ENTER': '\r', 'ESC': '\x1b', 'BACKSPACE': '\b',
                  'TAB': '\t', 'SPACE': ' ', 'MINUS': '-',
                  'EQUAL': '=', 'LEFT_BRACE': '[',
                  'RIGHT_BRACE': ']', 'BACKSLASH': '\\',
                  'SEMICOLON': ';',
                  'APOSTROPHE': '\'', 'GRAVE': '`',
                  'COMMA': ',', 'PERIOD': '.', 'FORWARD_SLASH': '/',
                  'RIGHT_ARROW': '\x1b[C', 'LEFT_ARROW':
                      '\x1b[D', 'DOWN_ARROW': '\x1b[B', 'UP_ARROW': '\x1b[A',
                  'sA': 'A', 'sB': 'B', 'sC': 'C', 'sD': 'D', 'sE': 'E', 'sF': 'F',
                  'sG': 'G', 'sH': 'H', 'sI': 'I', 'sJ': 'J', 'sK': 'K', 'sL': 'L',
                  'sM': 'M', 'sN': 'N', 'sO': 'O', 'sP': 'P',
                  'sQ': 'Q', 'sR': 'R', 'sS': 'S', 'sT': 'T', 'sU': 'U', 'sV': 'V',
                  'sW': 'W', 'sX': 'X', 'sY': 'Y', 'sZ': 'Z',
                  's1': '!', 's2': '@', 's3': '#', 's4': '$', 's5': '%', 's6': '^',
                  's7': '&', 's8': '*', 's9': '(', 's0': ')',
                  'sMINUS': '_',
                  'sEQUAL': '+', 'sLEFT_BRACE': '{',
                  'sRIGHT_BRACE': '}', 'sBACKSLASH': '|',
                  'sHASH_TILDE': '~', 'sSEMICOLON': ':',
                  'sAPOSTROPHE': '"', 'sGRAVE': '~',
                  'sCOMMA': '<', 'sPERIOD': '>', 'sFORWARD_SLASH': '?',
                  }

hid_key_none = 0x00
hid_key_left_control = 0x01
hid_key_left_shift = 0x02
hid_key_left_alt = 0x04
hid_key_left_meta = 0x08
hid_key_right_control = 0x10
hid_key_right_shift = 0x20
hid_key_right_alt = 0x40
hid_key_right_meta = 0x80

STX = 0x02
ETX = 0x03


class Terminal(IOBase):

    def __init__(self, columns, rows, uart_id, background=BLUE, foreground=YELLOW):
        self.uart = UART(uart_id, 115200)
        self.key_buffer = deque((), 10)
        self.screen = Screen(columns, rows)
        self.screen.dirty.clear()
        self.screen_buffer = [[None] * columns for _ in range(rows)]
        self.input_stream = Stream(self.screen)
        lcd = LCD(rate=42000000)
        self.lcd = lcd.initCh(color=foreground, font='Amstrad_8', scale=1)
        self.foreground = foreground
        self.background = background
        self.lcd.fillMonocolor(background)
        self.rows = rows
        self.columns = columns
        self.show_cursor = True
        self.cursor_delay = 200
        self.last_draw_cursor_time = time.ticks_ms()
        self.last_cursor_x = 0
        self.last_cursor_y = 0
        self.draw_cursor_in_progress = False

    def __del__(self):
        self.close()

    def read(self):
        data = self.uart.read(11)
        if data is not None:
            if (len(data) == 11) and (data[0] == STX) and (data[1] == 0x08) and (data[10] == ETX):
                return self.input_byte_array(data[2:10])
            else:
                for i in range(0, len(data)):
                    if data[i] == STX:
                        report = data[i:len(data)] + self.uart.read(11 - (len(data) - i))
                        if (len(report) == 11) and (report[0] == STX) and (report[1] == 0x08) and (report[10] == ETX):
                            return self.input_byte_array(report[2:10])

    def close(self):
        self.uart.deinit()

    def readinto(self, buf):
        key_input = self.read()
        self.draw_cursor()
        self._gcCollect()
        if key_input is not None:
            bytes_key_input = str.encode(key_input)
            count = len(key_input)
            for i in range(count):
                self.key_buffer.append(bytes_key_input[i])
        try:
            buf[0] = self.key_buffer.popleft()
            return 1
        except:
            pass

    @micropython.viper
    def _gcCollect(self):
        gc.collect()

    def write(self, buf):
        try:
            if self.screen.cursor.y == self.rows - 1:
                self.screen.reset()
                self.screen.dirty.clear()
                self.last_cursor_x = 0
                self.last_cursor_y = 0
                self.lcd.fillMonocolor(self.background)
            str_buf = str(buf, 'utf-8')
            if str_buf == "\x1b[K":
                self.clear_line(self.screen.cursor.x * 8 + 1,
                                self.screen.cursor.y * 8 + 1)

            for b in str_buf:
                self.input_stream.feed(b)
            del str_buf
            self.update_screen()
        except:
            pass

    def clear_line(self, x, y):
        self.lcd.drawHline(x, y, 320, self.background, 8)

    def draw_text(self, text, x, y, ):
        if text is None or text == ' ':
            self.lcd.drawHline(x, y, 8, self.background, 8)
        else:
            count = len(text)
            for i in range(count):
                if text[i] != ' ':
                    if text[i] == 'i' or text[i] == 'l':
                        offset = 2
                    else:
                        offset = 0
                    self.lcd.drawHline(x + i * 8, y, 8, self.background, 8)
                    self.lcd.printChar(text[i], x + i * 8 + offset, y)

    def update_screen(self):
        for dirty_row in self.screen.dirty:
            for column in range(self.columns):
                if self.screen_buffer[dirty_row][column] != self.screen.buffer[dirty_row][column].data:
                    self.draw_text(self.screen.buffer[dirty_row][column], column * 8 + 1, dirty_row * 8 + 1)
        self.screen.dirty.clear()
        for row in range(self.rows):
            for column in range(self.columns):
                self.screen_buffer[row][column] = self.screen.buffer[row][column].data

    @staticmethod
    def decode_key_modifier(code):
        key = ''
        if (code & hid_key_left_meta) | (code & hid_key_right_meta):
            key += "WIN-"
        if (code & hid_key_left_control) | (code & hid_key_right_control):
            key += "CTRL-"
        if (code & hid_key_left_shift) | (code & hid_key_right_shift):
            key += "SHIFT-"
        if (code & hid_key_left_alt) | (code & hid_key_right_alt):
            key += "ALT-"
        if len(key) > 0:
            key = key[:-1]

        return key

    @staticmethod
    def decode_key_codes(codes):
        key = ''
        for code in codes:
            if hid_key_code[code] is not None:
                key += hid_key_code[code] + "-"
        if len(key) > 0:
            key = key[:-1]
        return key

    @staticmethod
    def translate_code1(modifier, codes):
        ascii_code = ''
        shift = ""
        if 'SHIFT' in modifier:
            shift = 's'
        if codes is not None and len(codes) > 0:
            scan_codes = codes.split('-')
            for scan_code in scan_codes:
                if scan_code in key_code_ascii:
                    ascii_code += key_code_ascii[shift + scan_code]
        if len(ascii_code) == 0:
            return None
        return ascii_code

    @staticmethod
    def translate_code(modifier, code):
        shift = ""
        if (modifier & hid_key_left_shift) | (modifier & hid_key_right_shift) > 0:
            shift = 's'
        ascii_code = key_code_ascii[shift + hid_key_code[code]]
        if len(ascii_code) == 0:
            return None
        return ascii_code

    def input_byte_array(self, data):
        report_modifier = memoryview(data)[0:1]
        report_keys = memoryview(data)[2:3]
        # modifier = self.decode_key_modifier(report_modifier[0])
        # codes = self.decode_key_codes(report_keys)
        if report_keys[0] != 0:
            return self.translate_code(report_modifier[0], report_keys[0])

        return None

    def draw_cursor(self):
        if not self.draw_cursor_in_progress:
            self.draw_cursor_in_progress = True
            delta = time.ticks_diff(time.ticks_ms(), self.last_draw_cursor_time)

            if delta > self.cursor_delay:
                self._gcCollect()
                self.last_draw_cursor_time = time.ticks_ms()
                if self.show_cursor:
                    self.draw_text(self.screen_buffer[self.screen.cursor.y][self.screen.cursor.x],
                                   self.screen.cursor.x * 8 + 1,
                                   self.screen.cursor.y * 8 + 1)

                    self.show_cursor = False

                else:
                    self.show_cursor = True
                    self.lcd.drawHline(self.screen.cursor.x * 8 + 1,
                                       self.screen.cursor.y * 8 + 7, 8, self.foreground,
                                       1)
                    time.sleep_ms(500)

                    self.draw_text(self.screen_buffer[self.screen.cursor.y][self.screen.cursor.x],
                                   self.screen.cursor.x * 8 + 1,
                                   self.screen.cursor.y * 8 + 1)
            self.draw_cursor_in_progress = False
