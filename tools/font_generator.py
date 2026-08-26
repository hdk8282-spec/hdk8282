#!/usr/bin/env python3
"""
Pia Carrot he Youkoso!! 2.2 (GBC) - 한글 폰트 생성기 (Font Generator)

한글 완성형 글자를 GBC 2bpp 타일 데이터로 변환하여
ROM에 삽입할 수 있는 폰트 데이터를 생성합니다.

사용법:
    python font_generator.py [옵션]

옵션:
    --chars <파일>     사용할 한글 문자 목록 파일 (기본: korean_table.json 기반)
    --size <8|12|16>   폰트 크기 (기본: 8x8)
    --output <파일>    출력 파일 (기본: ./font_data.bin)
    --preview          터미널에 미리보기 출력
    --png <파일>       폰트 시트를 PNG로 저장 (Pillow 필요)

예시:
    python font_generator.py --size 8 --output font_8x8.bin --preview
    python font_generator.py --chars korean_table.json --png font_sheet.png
"""

import os
import sys
import json
import struct

# ============================================================
# GBC 2bpp 타일 형식
# ============================================================
# GBC 타일: 8x8 픽셀, 2bpp (2 bits per pixel)
# 각 행 = 2바이트 (lo plane + hi plane)
# 1 타일 = 16바이트
#
# 픽셀 값: 0=투명/흰, 1=밝은회색, 2=어두운회색, 3=검정
# 텍스트 폰트: 보통 0=배경, 3=글자 (1bpp처럼 사용)

BANK_SIZE = 0x4000  # 16KB per bank
TILE_WIDTH = 8
TILE_HEIGHT = 8
BYTES_PER_TILE = 16  # 8행 * 2바이트


# ============================================================
# 내장 8x8 한글 비트맵 폰트
# ============================================================
# 8x8 크기에서 한글을 표현하려면 조합형이 필요
# 초성(ㄱ-ㅎ) + 중성(ㅏ-ㅣ) + 종성(없음/ㄱ-ㅎ) 조합

# 한글 유니코드 분해
CHOSEONG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNGSEONG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONGSEONG = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'

def decompose_hangul(char):
    """한글 완성형 문자를 초성/중성/종성으로 분해"""
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3:
        offset = code - 0xAC00
        cho = offset // (21 * 28)
        jung = (offset % (21 * 28)) // 28
        jong = offset % 28
        return cho, jung, jong
    return None


# 8x8 초성 비트맵 (간소화된 형태)
# 각 초성은 4x4 또는 4x3 크기의 비트맵으로 표현
# 종성 유무와 중성 형태에 따라 배치가 달라짐

# 초성 비트맵 (상단 왼쪽 배치, 받침 없는 경우)
CHOSEONG_BITMAPS_NO_JONG = {
    0: [  # ㄱ
        0b1111,
        0b0001,
        0b0010,
        0b0100,
    ],
    1: [  # ㄲ
        0b1111,
        0b0101,
        0b1010,
        0b0000,
    ],
    2: [  # ㄴ
        0b1000,
        0b1000,
        0b1000,
        0b1111,
    ],
    3: [  # ㄷ
        0b1111,
        0b1000,
        0b1000,
        0b1111,
    ],
    4: [  # ㄸ
        0b1111,
        0b1010,
        0b1010,
        0b1111,
    ],
    5: [  # ㄹ
        0b1111,
        0b0001,
        0b1111,
        0b1000,
    ],
    6: [  # ㅁ
        0b1111,
        0b1001,
        0b1001,
        0b1111,
    ],
    7: [  # ㅂ
        0b1010,
        0b1010,
        0b1111,
        0b1001,
    ],
    8: [  # ㅃ
        0b1010,
        0b1111,
        0b1010,
        0b1111,
    ],
    9: [  # ㅅ
        0b0010,
        0b0101,
        0b1000,
        0b0000,
    ],
    10: [  # ㅆ
        0b0101,
        0b1010,
        0b0100,
        0b0000,
    ],
    11: [  # ㅇ
        0b0110,
        0b1001,
        0b1001,
        0b0110,
    ],
    12: [  # ㅈ
        0b0100,
        0b1110,
        0b0001,
        0b1111,
    ],
    13: [  # ㅉ
        0b1010,
        0b0111,
        0b1010,
        0b1111,
    ],
    14: [  # ㅊ
        0b0100,
        0b1110,
        0b0001,
        0b1111,
    ],
    15: [  # ㅋ
        0b1111,
        0b0010,
        0b1111,
        0b0100,
    ],
    16: [  # ㅌ
        0b1111,
        0b0010,
        0b1111,
        0b1111,
    ],
    17: [  # ㅍ
        0b1111,
        0b0101,
        0b0101,
        0b1111,
    ],
    18: [  # ㅎ
        0b0100,
        0b1111,
        0b0110,
        0b0110,
    ],
}

# 중성 비트맵 유형 분류
# 유형 1: 세로 모음 (ㅏㅐㅑㅒㅓㅔㅕㅖㅣ) - 초성 오른쪽에 배치
# 유형 2: 가로 모음 (ㅗㅛㅜㅠㅡ) - 초성 아래에 배치
# 유형 3: 복합 모음 (ㅘㅙㅚㅝㅞㅟㅢ) - 오른쪽+아래

JUNG_TYPE = {
    0: 1,   # ㅏ
    1: 1,   # ㅐ
    2: 1,   # ㅑ
    3: 1,   # ㅒ
    4: 1,   # ㅓ
    5: 1,   # ㅔ
    6: 1,   # ㅕ
    7: 1,   # ㅖ
    8: 2,   # ㅗ
    9: 3,   # ㅘ
    10: 3,  # ㅙ
    11: 3,  # ㅚ
    12: 2,  # ㅛ
    13: 2,  # ㅜ
    14: 3,  # ㅝ
    15: 3,  # ㅞ
    16: 3,  # ㅟ
    17: 2,  # ㅠ
    18: 2,  # ㅡ
    19: 3,  # ㅢ
    20: 1,  # ㅣ
}


def render_hangul_8x8(char):
    """
    한글 완성형 문자를 8x8 비트맵으로 렌더링합니다.
    
    Returns:
        list: 8개 바이트 (각 바이트 = 1행, MSB = 왼쪽)
    """
    result = decompose_hangul(char)
    if result is None:
        return render_symbol_8x8(char)
    
    cho, jung, jong = result
    has_jong = jong > 0
    jung_type = JUNG_TYPE.get(jung, 1)
    
    # 8x8 캔버스 초기화
    canvas = [[0] * 8 for _ in range(8)]
    
    # 초성 배치
    cho_bitmap = CHOSEONG_BITMAPS_NO_JONG.get(cho, [0, 0, 0, 0])
    
    if jung_type == 1:  # 세로 모음 (ㅏ 계열)
        # 초성: 왼쪽 상단 4x4 (또는 4x5)
        cho_rows = 5 if not has_jong else 3
        cho_cols = 5
        for row in range(min(len(cho_bitmap), cho_rows)):
            for col in range(4):
                if cho_bitmap[row] & (0b1000 >> col):
                    canvas[row][col] = 1
        
        # 중성: 오른쪽 세로선
        if jung in [0, 2]:  # ㅏ, ㅑ
            for row in range(7 if not has_jong else 5):
                canvas[row][5] = 1
            canvas[2][6] = 1
            if jung == 2:  # ㅑ
                canvas[1][6] = 1
                canvas[3][6] = 1
        elif jung in [4, 6]:  # ㅓ, ㅕ
            for row in range(7 if not has_jong else 5):
                canvas[row][6] = 1
            canvas[2][5] = 1
            if jung == 6:  # ㅕ
                canvas[1][5] = 1
                canvas[3][5] = 1
        elif jung in [1, 3]:  # ㅐ, ㅒ
            for row in range(7 if not has_jong else 5):
                canvas[row][5] = 1
                canvas[row][7] = 1
            canvas[2][6] = 1
        elif jung in [5, 7]:  # ㅔ, ㅖ
            for row in range(7 if not has_jong else 5):
                canvas[row][5] = 1
                canvas[row][7] = 1
            canvas[2][6] = 1
        elif jung == 20:  # ㅣ
            for row in range(7 if not has_jong else 5):
                canvas[row][6] = 1
    
    elif jung_type == 2:  # 가로 모음 (ㅗ 계열)
        # 초성: 상단 중앙 넓게
        for row in range(min(len(cho_bitmap), 3)):
            for col in range(4):
                if cho_bitmap[row] & (0b1000 >> col):
                    canvas[row][col + 2] = 1
        
        # 중성: 가로선
        if jung == 8:  # ㅗ
            canvas[4][3] = 1
            for col in range(1, 7):
                canvas[5 if not has_jong else 4][col] = 1
        elif jung == 12:  # ㅛ
            canvas[3][2] = 1
            canvas[3][4] = 1
            for col in range(1, 7):
                canvas[4][col] = 1
        elif jung == 13:  # ㅜ
            for col in range(1, 7):
                canvas[4][col] = 1
            canvas[5][3] = 1
        elif jung == 17:  # ㅠ
            for col in range(1, 7):
                canvas[4][col] = 1
            canvas[5][2] = 1
            canvas[5][4] = 1
        elif jung == 18:  # ㅡ
            for col in range(1, 7):
                canvas[4 if not has_jong else 3][col] = 1
    
    elif jung_type == 3:  # 복합 모음
        # 초성: 왼쪽 상단 작게
        for row in range(min(len(cho_bitmap), 3)):
            for col in range(3):
                if cho_bitmap[row] & (0b1000 >> col):
                    canvas[row][col] = 1
        
        # 복합 중성 처리 (간소화)
        if jung == 9:  # ㅘ
            for col in range(1, 6):
                canvas[3][col] = 1
            canvas[2][3] = 1
            for row in range(0, 5):
                canvas[row][6] = 1
            canvas[2][7] = 1
        elif jung == 14:  # ㅝ
            for col in range(1, 6):
                canvas[3][col] = 1
            canvas[4][3] = 1
            for row in range(0, 5):
                canvas[row][6] = 1
            canvas[2][5] = 1
        else:
            # 기타 복합 모음 기본 처리
            for col in range(2, 6):
                canvas[3][col] = 1
            for row in range(0, 5):
                canvas[row][6] = 1
    
    # 종성 배치
    if has_jong:
        jong_bitmap = CHOSEONG_BITMAPS_NO_JONG.get(jong - 1, [0, 0, 0, 0])
        jong_start_row = 6 if jung_type == 1 else 6
        for row in range(min(len(jong_bitmap), 2)):
            for col in range(4):
                if jong_bitmap[row] & (0b1000 >> col):
                    x = col + 1 if jung_type == 1 else col + 2
                    if x < 8 and jong_start_row + row < 8:
                        canvas[jong_start_row + row][x] = 1
    
    # 캔버스를 바이트 배열로 변환
    bitmap = []
    for row in range(8):
        byte_val = 0
        for col in range(8):
            if canvas[row][col]:
                byte_val |= (0x80 >> col)
        bitmap.append(byte_val)
    
    return bitmap


def render_symbol_8x8(char):
    """기호, 숫자, 영문 등을 8x8 비트맵으로 렌더링"""
    # 기본 ASCII 기호의 간단한 비트맵
    SYMBOL_BITMAPS = {
        ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
        '!': [0x10, 0x10, 0x10, 0x10, 0x10, 0x00, 0x10, 0x00],
        '?': [0x3C, 0x42, 0x02, 0x0C, 0x10, 0x00, 0x10, 0x00],
        '.': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x00],
        ',': [0x00, 0x00, 0x00, 0x00, 0x00, 0x08, 0x08, 0x10],
        '…': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x54, 0x00],
        '「': [0x3C, 0x20, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00],
        '」': [0x00, 0x00, 0x00, 0x00, 0x04, 0x04, 0x3C, 0x00],
        '～': [0x00, 0x00, 0x00, 0x32, 0x4C, 0x00, 0x00, 0x00],
        '♪': [0x04, 0x06, 0x05, 0x04, 0x04, 0x1C, 0x1C, 0x00],
        '♡': [0x00, 0x36, 0x49, 0x41, 0x22, 0x14, 0x08, 0x00],
        '（': [0x04, 0x08, 0x10, 0x10, 0x10, 0x08, 0x04, 0x00],
        '）': [0x20, 0x10, 0x08, 0x08, 0x08, 0x10, 0x20, 0x00],
    }
    
    # 숫자 비트맵
    DIGIT_BITMAPS = {
        '0': [0x3C, 0x42, 0x46, 0x4A, 0x52, 0x62, 0x3C, 0x00],
        '1': [0x08, 0x18, 0x08, 0x08, 0x08, 0x08, 0x1C, 0x00],
        '2': [0x3C, 0x42, 0x02, 0x0C, 0x30, 0x40, 0x7E, 0x00],
        '3': [0x3C, 0x42, 0x02, 0x1C, 0x02, 0x42, 0x3C, 0x00],
        '4': [0x04, 0x0C, 0x14, 0x24, 0x7E, 0x04, 0x04, 0x00],
        '5': [0x7E, 0x40, 0x7C, 0x02, 0x02, 0x42, 0x3C, 0x00],
        '6': [0x1C, 0x20, 0x40, 0x7C, 0x42, 0x42, 0x3C, 0x00],
        '7': [0x7E, 0x02, 0x04, 0x08, 0x10, 0x10, 0x10, 0x00],
        '8': [0x3C, 0x42, 0x42, 0x3C, 0x42, 0x42, 0x3C, 0x00],
        '9': [0x3C, 0x42, 0x42, 0x3E, 0x02, 0x04, 0x38, 0x00],
    }
    
    # 영문 대문자 (간소화)
    ALPHA_BITMAPS = {
        'A': [0x18, 0x24, 0x42, 0x7E, 0x42, 0x42, 0x42, 0x00],
        'B': [0x7C, 0x42, 0x42, 0x7C, 0x42, 0x42, 0x7C, 0x00],
        'C': [0x3C, 0x42, 0x40, 0x40, 0x40, 0x42, 0x3C, 0x00],
        'D': [0x78, 0x44, 0x42, 0x42, 0x42, 0x44, 0x78, 0x00],
        'E': [0x7E, 0x40, 0x40, 0x7C, 0x40, 0x40, 0x7E, 0x00],
        'F': [0x7E, 0x40, 0x40, 0x7C, 0x40, 0x40, 0x40, 0x00],
        'G': [0x3C, 0x42, 0x40, 0x4E, 0x42, 0x42, 0x3C, 0x00],
        'H': [0x42, 0x42, 0x42, 0x7E, 0x42, 0x42, 0x42, 0x00],
        'I': [0x3E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x3E, 0x00],
        'J': [0x1E, 0x04, 0x04, 0x04, 0x04, 0x44, 0x38, 0x00],
        'K': [0x42, 0x44, 0x48, 0x70, 0x48, 0x44, 0x42, 0x00],
        'L': [0x40, 0x40, 0x40, 0x40, 0x40, 0x40, 0x7E, 0x00],
        'M': [0x42, 0x66, 0x5A, 0x42, 0x42, 0x42, 0x42, 0x00],
        'N': [0x42, 0x62, 0x52, 0x4A, 0x46, 0x42, 0x42, 0x00],
        'O': [0x3C, 0x42, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00],
        'P': [0x7C, 0x42, 0x42, 0x7C, 0x40, 0x40, 0x40, 0x00],
        'Q': [0x3C, 0x42, 0x42, 0x42, 0x4A, 0x44, 0x3A, 0x00],
        'R': [0x7C, 0x42, 0x42, 0x7C, 0x48, 0x44, 0x42, 0x00],
        'S': [0x3C, 0x42, 0x40, 0x3C, 0x02, 0x42, 0x3C, 0x00],
        'T': [0x7F, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x00],
        'U': [0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00],
        'V': [0x42, 0x42, 0x42, 0x42, 0x24, 0x24, 0x18, 0x00],
        'W': [0x42, 0x42, 0x42, 0x42, 0x5A, 0x66, 0x42, 0x00],
        'X': [0x42, 0x42, 0x24, 0x18, 0x24, 0x42, 0x42, 0x00],
        'Y': [0x41, 0x22, 0x14, 0x08, 0x08, 0x08, 0x08, 0x00],
        'Z': [0x7E, 0x02, 0x04, 0x08, 0x10, 0x20, 0x7E, 0x00],
    }
    
    if char in SYMBOL_BITMAPS:
        return SYMBOL_BITMAPS[char]
    elif char in DIGIT_BITMAPS:
        return DIGIT_BITMAPS[char]
    elif char.upper() in ALPHA_BITMAPS:
        bitmap = ALPHA_BITMAPS[char.upper()]
        if char.islower():
            # 소문자는 2픽셀 아래로 이동 + 축소 (간소화)
            return [0x00, 0x00] + bitmap[:6]
        return bitmap
    else:
        # 알 수 없는 문자: 빈 박스
        return [0x7E, 0x42, 0x42, 0x42, 0x42, 0x42, 0x7E, 0x00]


# ============================================================
# GBC 2bpp 타일 변환
# ============================================================
def bitmap_to_2bpp_tile(bitmap, color=3):
    """
    1bpp 비트맵(8바이트)을 GBC 2bpp 타일(16바이트)로 변환합니다.
    
    Args:
        bitmap: 8개 바이트 리스트 (각 바이트 = 1행)
        color: 글자 색상 (1=밝은회, 2=어두운회, 3=검정)
    
    Returns:
        bytes: 16바이트 2bpp 타일 데이터
    """
    tile_data = bytearray(16)
    
    for row in range(8):
        pixel_byte = bitmap[row] if row < len(bitmap) else 0
        
        if color == 3:  # 검정 (both planes = 1)
            tile_data[row * 2] = pixel_byte       # Low plane
            tile_data[row * 2 + 1] = pixel_byte   # High plane
        elif color == 2:  # 어두운 회색 (hi=1, lo=0)
            tile_data[row * 2] = 0x00
            tile_data[row * 2 + 1] = pixel_byte
        elif color == 1:  # 밝은 회색 (hi=0, lo=1)
            tile_data[row * 2] = pixel_byte
            tile_data[row * 2 + 1] = 0x00
    
    return bytes(tile_data)


# ============================================================
# 폰트 생성 메인 함수
# ============================================================
def generate_font(char_list, output_path, preview=False):
    """
    한글 문자 목록에 대한 폰트 타일 데이터를 생성합니다.
    
    Args:
        char_list: 문자 리스트 (순서대로 타일 인덱스 배정)
        output_path: 출력 바이너리 파일 경로
        preview: True면 터미널에 미리보기 출력
    
    Returns:
        bytes: 전체 폰트 타일 데이터
    """
    all_tile_data = bytearray()
    
    print(f"폰트 생성 중: {len(char_list)}개 문자")
    print()
    
    for idx, char in enumerate(char_list):
        # 비트맵 렌더링
        bitmap = render_hangul_8x8(char)
        
        # 2bpp 타일 변환
        tile = bitmap_to_2bpp_tile(bitmap, color=3)
        all_tile_data.extend(tile)
        
        # 미리보기 출력 (처음 20자만)
        if preview and idx < 20:
            print(f"  [{idx:4d}] '{char}' (U+{ord(char):04X}):")
            for row in range(8):
                line = ""
                byte_val = bitmap[row]
                for bit in range(7, -1, -1):
                    if byte_val & (1 << bit):
                        line += "██"
                    else:
                        line += "  "
                print(f"    {line}")
            print()
    
    # 파일 저장
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(all_tile_data)
    
    print(f"폰트 데이터 생성 완료:")
    print(f"  문자 수: {len(char_list)}")
    print(f"  타일 크기: 8x8 2bpp")
    print(f"  데이터 크기: {len(all_tile_data):,} bytes ({len(all_tile_data)//1024} KB)")
    print(f"  출력 파일: {output_path}")
    
    return bytes(all_tile_data)


def generate_font_from_table(table_path, output_path, preview=False):
    """korean_table.json에서 문자 목록을 읽어 폰트를 생성합니다."""
    
    with open(table_path, 'r', encoding='utf-8') as f:
        table = json.load(f)
    
    # 바이트 순서대로 정렬하여 문자 목록 생성
    sorted_entries = sorted(table.items(), 
                           key=lambda x: (x[1]['page'], x[1]['char_code']))
    
    char_list = [char for char, _ in sorted_entries]
    
    return generate_font(char_list, output_path, preview)


# ============================================================
# ROM에 폰트 삽입
# ============================================================
def insert_font_into_rom(rom_path, font_data_path, output_path, font_bank_start=196):
    """
    생성된 폰트 데이터를 ROM의 빈 뱅크에 삽입합니다.
    
    Args:
        rom_path: 원본 ROM 경로
        font_data_path: 폰트 바이너리 데이터 경로
        output_path: 출력 ROM 경로
        font_bank_start: 폰트를 저장할 시작 뱅크 번호
    """
    print(f"\n폰트 ROM 삽입:")
    
    with open(rom_path, 'rb') as f:
        rom = bytearray(f.read())
    
    with open(font_data_path, 'rb') as f:
        font_data = f.read()
    
    # 필요한 뱅크 수 계산
    banks_needed = (len(font_data) + BANK_SIZE - 1) // BANK_SIZE
    print(f"  폰트 크기: {len(font_data):,} bytes")
    print(f"  필요 뱅크: {banks_needed}개 (Bank {font_bank_start}-{font_bank_start+banks_needed-1})")
    
    # 폰트 데이터 삽입
    for i in range(banks_needed):
        bank_num = font_bank_start + i
        bank_offset = bank_num * BANK_SIZE
        
        start = i * BANK_SIZE
        end = min(start + BANK_SIZE, len(font_data))
        chunk = font_data[start:end]
        
        # 뱅크 크기로 패딩
        if len(chunk) < BANK_SIZE:
            chunk = chunk + bytes(BANK_SIZE - len(chunk))
        
        rom[bank_offset:bank_offset + BANK_SIZE] = chunk
        print(f"  Bank {bank_num} (0x{bank_offset:06X}): {end-start} bytes 기록")
    
    # 체크섬 수정
    # 헤더 체크섬
    checksum = 0
    for i in range(0x0134, 0x014D):
        checksum = (checksum - rom[i] - 1) & 0xFF
    rom[0x014D] = checksum
    
    # 글로벌 체크섬
    rom[0x014E] = 0
    rom[0x014F] = 0
    total = sum(rom) & 0xFFFF
    rom[0x014E] = (total >> 8) & 0xFF
    rom[0x014F] = total & 0xFF
    
    with open(output_path, 'wb') as f:
        f.write(rom)
    
    print(f"  출력: {output_path}")
    print(f"  폰트 뱅크 위치: Bank {font_bank_start} (0x{font_bank_start*BANK_SIZE:06X})")


# ============================================================
# 진입점
# ============================================================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pia Carrot 2.2 GBC 한글 폰트 생성기')
    parser.add_argument('--chars', type=str, default=None,
                       help='한글 문자 테이블 JSON 파일 (korean_table.json)')
    parser.add_argument('--size', type=int, default=8, choices=[8],
                       help='폰트 크기 (현재 8x8만 지원)')
    parser.add_argument('--output', type=str, default='./font_data.bin',
                       help='출력 폰트 바이너리 파일')
    parser.add_argument('--preview', action='store_true',
                       help='터미널에 미리보기 출력')
    parser.add_argument('--rom', type=str, default=None,
                       help='폰트를 삽입할 ROM 파일')
    parser.add_argument('--rom-output', type=str, default=None,
                       help='폰트가 삽입된 ROM 출력 파일')
    parser.add_argument('--font-bank', type=int, default=196,
                       help='폰트 데이터를 저장할 시작 뱅크 (기본: 196)')
    
    args = parser.parse_args()
    
    # 문자 목록 결정
    if args.chars and os.path.exists(args.chars):
        print(f"문자 테이블 로드: {args.chars}")
        generate_font_from_table(args.chars, args.output, args.preview)
    else:
        # 기본 한글 문자 목록 (자주 사용되는 글자)
        default_chars = (
            ' 、。！？…・「」0123456789'
            '가각간갈감갑강같개객거건걸검것게겨격견결경계고곡곤골공과관광괜교구국군굴궁권귀규균그극근글금급기긴길김까꺼꼬꼭꽃꿈끄끌끝끼'
            '나난날남낮내너널넘네녀년념노놀농높누눈눌느늘능니닌님다단달담답당대더덕던덜덤도독돈돌동두둘뒤드들듬등디딩따때떠떨또뚜뛰뜨'
            '라란랄람래러런럴렇레려력련렬로론롤료루룰류르른를름리린릴림마만말많맘맛망매머먹먼멀멍메면명모목몰몸못무문물뭐므미민밀밝밤방배'
            '백번벌범법별병보복본볼봐부북분불붙브비빈빌빠빨뻐사산살삼상새생서석선설섬성세소속손솔송수숙순술쉬스슬습시식신실심십싶싸써쓰씨'
            '아악안않알앉암앞애야약양어억언얼엄없었에여역연열영예오온올옮왜외요용우운울움원월위유육은을음응의이인일읽임입있자작잔잘잠장재'
            '저적전절점접정제조족존졸종좀좋주죽준줄중쥐즈즐증지직진질짐집징차찬참창찾채처천철청체초총추춘출충취츠측치친칠침카켜코크큰클키'
            '타탈태터턴통투특틀티파팔펴편평포표푸풀피필하학한할함합항해행허험헤혀현형혹혼홀화확환활황회효후훌휴흐흑흔흥희흰히힘'
        )
        
        char_list = list(dict.fromkeys(default_chars))  # 중복 제거, 순서 유지
        print(f"기본 한글 문자 목록 사용: {len(char_list)}개")
        generate_font(char_list, args.output, args.preview)
    
    # ROM 삽입 옵션
    if args.rom and args.rom_output:
        insert_font_into_rom(args.rom, args.output, args.rom_output, args.font_bank)
