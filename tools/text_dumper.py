#!/usr/bin/env python3
"""
Pia Carrot he Youkoso!! 2.2 (GBC) - 텍스트 추출기 (Text Dumper)

이 스크립트는 ROM에서 모든 텍스트 데이터를 추출하여
번역 가능한 형태의 텍스트 파일로 저장합니다.

사용법:
    python text_dumper.py <rom_file> [output_dir]

예시:
    python text_dumper.py "Pia Carrot he Youkoso!! 2.2.gbc" ./dump
"""

import os
import sys
import json
from collections import OrderedDict

# ============================================================
# ROM 구조 상수
# ============================================================
BANK_SIZE = 0x4000  # 16KB per bank

# 스크립트 뱅크: 이벤트 제어 및 텍스트 참조 포함
SCRIPT_BANKS = list(range(46, 57))  # Bank 46-56

# 텍스트 뱅크: 실제 텍스트 데이터 저장
TEXT_BANKS = list(range(152, 196))  # Bank 152-195

# 제어코드 정의
CONTROL_CODES = {
    # 종료/흐름 제어 (첫 바이트 0x00 + 두 번째 바이트)
    (0x00, 0xFF): "[END]",           # 텍스트 블록 종료
    (0x00, 0xFE): "[NEWLINE]",       # 줄바꿈
    (0x00, 0xFC): "[PAGE]",          # 페이지 넘김 (버튼 대기)
    (0x00, 0xFA): "[WAIT]",          # 입력 대기
    (0x00, 0xF8): "[PAUSE]",         # 특수 대기
    (0x00, 0xF0): "[CTRL_F0]",       # 미확인 제어
    # 변수 삽입
    (0x05, 0x44): "[PLAYER_NAME]",   # 플레이어 이름 변수
}

# 줄 끝 명령 (XX 03 형식)
LINE_END_CODES = {
    0x08: "[LINE_END_08]",
    0x09: "[LINE_END_09]",
    0x0A: "[LINE_END_0A]",
    0x0B: "[LINE_END_0B]",
    0x0C: "[LINE_END_0C]",
    0x0D: "[LINE_END_0D]",
    0x0E: "[LINE_END_0E]",
    0x0F: "[LINE_END_0F]",
    0x10: "[LINE_END_10]",
    0x11: "[LINE_END_11]",
    0x12: "[LINE_END_12]",
    0x13: "[LINE_END_13]",
    0x19: "[LINE_END_19]",
}


# ============================================================
# 텍스트 참조 추출
# ============================================================
def extract_text_references(rom_data):
    """스크립트 뱅크에서 모든 텍스트 참조를 추출합니다."""
    references = []
    
    for script_bank in SCRIPT_BANKS:
        base = script_bank * BANK_SIZE
        bank_data = rom_data[base:base + BANK_SIZE]
        
        for i in range(len(bank_data) - 4):
            # 패턴: 19 [addr_lo] [addr_hi] [text_bank] 1B
            if bank_data[i] == 0x19 and bank_data[i + 4] == 0x1B:
                addr_lo = bank_data[i + 1]
                addr_hi = bank_data[i + 2]
                text_bank = bank_data[i + 3]
                addr = addr_lo | (addr_hi << 8)
                
                # 유효한 뱅크 주소 범위 확인 (0x4000-0x7FFF)
                if 0x4000 <= addr <= 0x7FFF and text_bank in TEXT_BANKS:
                    rom_offset = text_bank * BANK_SIZE + (addr - 0x4000)
                    references.append({
                        'script_bank': script_bank,
                        'script_offset': base + i,
                        'text_bank': text_bank,
                        'text_addr': addr,
                        'rom_offset': rom_offset,
                    })
    
    return references


# ============================================================
# 텍스트 블록 파싱
# ============================================================
def parse_text_block(rom_data, rom_offset):
    """
    ROM 오프셋에서 텍스트 블록 하나를 파싱합니다.
    
    Returns:
        (parsed_elements, raw_bytes, end_offset)
        - parsed_elements: 텍스트/제어코드 요소 리스트
        - raw_bytes: 원본 바이트 데이터
        - end_offset: 블록 종료 위치
    """
    elements = []
    raw_bytes = bytearray()
    i = rom_offset
    max_length = 4096  # 안전 제한 (무한루프 방지)
    
    while i < len(rom_data) - 1 and (i - rom_offset) < max_length:
        b1 = rom_data[i]
        b2 = rom_data[i + 1]
        
        # 제어코드 확인 (00 XX 형태)
        if b1 == 0x00 and b2 in [0xFF, 0xFE, 0xFC, 0xFA, 0xF8, 0xF0]:
            ctrl = CONTROL_CODES.get((b1, b2), f"[CTRL_{b1:02X}_{b2:02X}]")
            elements.append({'type': 'control', 'code': ctrl, 'bytes': [b1, b2]})
            raw_bytes.extend([b1, b2])
            i += 2
            
            # 텍스트 종료
            if b2 == 0xFF:
                break
            continue
        
        # 줄 끝 명령 (XX 03 형태)
        if b2 == 0x03 and b1 in LINE_END_CODES:
            ctrl = LINE_END_CODES[b1]
            elements.append({'type': 'control', 'code': ctrl, 'bytes': [b1, b2]})
            raw_bytes.extend([b1, b2])
            i += 2
            continue
        
        # 변수 삽입 (05 44)
        if b1 == 0x05 and b2 == 0x44:
            elements.append({'type': 'control', 'code': '[PLAYER_NAME]', 'bytes': [b1, b2]})
            raw_bytes.extend([b1, b2])
            i += 2
            continue
        
        # 일반 문자 (2바이트: [char_code][page])
        elements.append({
            'type': 'char',
            'char_code': b1,
            'page': b2,
            'bytes': [b1, b2]
        })
        raw_bytes.extend([b1, b2])
        i += 2
    
    return elements, bytes(raw_bytes), i


# ============================================================
# 텍스트 포맷터
# ============================================================
def format_text_block(elements):
    """파싱된 텍스트 요소를 읽기 쉬운 형태로 변환합니다."""
    result = ""
    
    for elem in elements:
        if elem['type'] == 'control':
            result += elem['code']
        elif elem['type'] == 'char':
            # 문자를 hex 표기로 표시 (실제 문자 매핑 전까지)
            char_code = elem['char_code']
            page = elem['page']
            if page == 0x00:
                result += f"<{char_code:02X}>"
            else:
                result += f"<{char_code:02X}:{page:02X}>"
    
    return result


def format_text_block_raw_hex(elements):
    """원본 hex 형태로 표시합니다."""
    parts = []
    for elem in elements:
        hex_str = ' '.join(f"{b:02X}" for b in elem['bytes'])
        parts.append(hex_str)
    return ' '.join(parts)


# ============================================================
# 메인 덤프 함수
# ============================================================
def dump_all_text(rom_path, output_dir):
    """ROM에서 모든 텍스트를 추출하여 파일로 저장합니다."""
    
    print(f"ROM 파일 로딩: {rom_path}")
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    
    print(f"ROM 크기: {len(rom_data):,} bytes ({len(rom_data) // 1024} KB)")
    print()
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 텍스트 참조 추출
    print("텍스트 참조 추출 중...")
    references = extract_text_references(rom_data)
    print(f"  총 텍스트 참조: {len(references)}개")
    
    # 중복 제거 (같은 ROM 오프셋을 가리키는 참조)
    unique_offsets = sorted(set(ref['rom_offset'] for ref in references))
    print(f"  고유 텍스트 블록: {len(unique_offsets)}개")
    print()
    
    # 2. 텍스트 블록 파싱 및 저장
    print("텍스트 블록 파싱 중...")
    
    # 텍스트 뱅크별로 분류
    bank_texts = {}
    for offset in unique_offsets:
        bank_num = offset // BANK_SIZE
        if bank_num not in bank_texts:
            bank_texts[bank_num] = []
        bank_texts[bank_num].append(offset)
    
    total_blocks = 0
    total_chars = 0
    all_unique_chars = set()
    
    # 뱅크별 덤프 파일 생성
    for bank_num in sorted(bank_texts.keys()):
        offsets = sorted(bank_texts[bank_num])
        bank_output = []
        
        for idx, offset in enumerate(offsets):
            elements, raw_bytes, end_offset = parse_text_block(rom_data, offset)
            formatted = format_text_block(elements)
            
            # 고유 문자 수집
            for elem in elements:
                if elem['type'] == 'char':
                    all_unique_chars.add((elem['char_code'], elem['page']))
                    total_chars += 1
            
            block_entry = {
                'id': f"B{bank_num:03d}_{idx:04d}",
                'rom_offset': f"0x{offset:06X}",
                'size': len(raw_bytes),
                'text': formatted,
                'raw_hex': raw_bytes.hex().upper(),
                'translation': "",  # 번역자가 채울 필드
            }
            bank_output.append(block_entry)
            total_blocks += 1
        
        # JSON 형식으로 저장
        json_path = os.path.join(output_dir, f"bank_{bank_num:03d}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(bank_output, f, ensure_ascii=False, indent=2)
        
        # 읽기 쉬운 텍스트 형식도 저장
        txt_path = os.path.join(output_dir, f"bank_{bank_num:03d}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Pia Carrot he Youkoso!! 2.2 - Text Bank {bank_num}\n")
            f.write(f"# 텍스트 블록 수: {len(offsets)}\n")
            f.write(f"# 형식: [ID] @ [ROM주소] (크기)\n")
            f.write(f"# 번역 시 'text:' 줄의 내용을 한국어로 교체하세요\n")
            f.write("=" * 70 + "\n\n")
            
            for entry in bank_output:
                f.write(f"[{entry['id']}] @ {entry['rom_offset']} ({entry['size']} bytes)\n")
                f.write(f"text: {entry['text']}\n")
                f.write(f"translated: \n")
                f.write("-" * 50 + "\n")
        
        print(f"  Bank {bank_num:3d}: {len(offsets):4d} 블록 저장됨")
    
    # 3. 문자 테이블 (사용된 모든 문자) 저장
    char_table_path = os.path.join(output_dir, "char_table.json")
    char_table = {}
    for char_code, page in sorted(all_unique_chars):
        key = f"{char_code:02X}_{page:02X}"
        char_table[key] = {
            'char_code': char_code,
            'page': page,
            'hex': f"{char_code:02X} {page:02X}",
            'mapped_char': '',  # 실제 일본어 문자 매핑 (수동 입력 필요)
            'korean_char': '',  # 한국어 대체 문자
        }
    
    with open(char_table_path, 'w', encoding='utf-8') as f:
        json.dump(char_table, f, ensure_ascii=False, indent=2)
    
    # 4. 스크립트 맵 (어떤 스크립트가 어떤 텍스트를 참조하는지)
    script_map_path = os.path.join(output_dir, "script_map.json")
    script_map = {}
    for ref in references:
        key = f"S{ref['script_bank']:03d}_0x{ref['script_offset']:06X}"
        script_map[key] = {
            'script_bank': ref['script_bank'],
            'script_offset': f"0x{ref['script_offset']:06X}",
            'text_bank': ref['text_bank'],
            'text_addr': f"0x{ref['text_addr']:04X}",
            'rom_offset': f"0x{ref['rom_offset']:06X}",
        }
    
    with open(script_map_path, 'w', encoding='utf-8') as f:
        json.dump(script_map, f, ensure_ascii=False, indent=2)
    
    # 5. 통계 요약
    print()
    print("=" * 50)
    print("추출 완료!")
    print(f"  총 텍스트 블록: {total_blocks:,}개")
    print(f"  총 문자 수: {total_chars:,}개")
    print(f"  고유 문자 종류: {len(all_unique_chars):,}개")
    print(f"  텍스트 뱅크: {len(bank_texts)}개")
    print(f"  출력 디렉토리: {output_dir}")
    print()
    print("생성된 파일:")
    print(f"  - bank_XXX.json : 뱅크별 텍스트 데이터 (JSON)")
    print(f"  - bank_XXX.txt  : 뱅크별 텍스트 (읽기용)")
    print(f"  - char_table.json : 문자 테이블")
    print(f"  - script_map.json : 스크립트-텍스트 매핑")
    
    return total_blocks, total_chars, len(all_unique_chars)


# ============================================================
# 진입점
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    rom_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './dump'
    
    if not os.path.exists(rom_path):
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        sys.exit(1)
    
    dump_all_text(rom_path, output_dir)
