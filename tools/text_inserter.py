#!/usr/bin/env python3
"""
Pia Carrot he Youkoso!! 2.2 (GBC) - 텍스트 삽입기 (Text Inserter)

번역된 한글 텍스트를 ROM에 삽입하여 한글화 패치 ROM을 생성합니다.

사용법:
    python text_inserter.py <원본_rom> <번역_디렉토리> <출력_rom>

예시:
    python text_inserter.py "Pia Carrot he Youkoso!! 2.2.gbc" ./translated "Pia_Carrot_KR.gbc"

번역 파일 형식:
    ./translated/bank_152.json  (text_dumper.py로 추출한 JSON에 'translation' 필드를 채움)
    ./translated/korean_table.json  (한글 문자 매핑 테이블)
"""

import os
import sys
import json
import copy
from collections import OrderedDict

# ============================================================
# ROM 구조 상수
# ============================================================
BANK_SIZE = 0x4000  # 16KB per bank

# 스크립트 뱅크 (텍스트 참조 포인터 위치)
SCRIPT_BANKS = list(range(46, 57))

# 텍스트 뱅크
TEXT_BANKS = list(range(152, 196))

# 제어코드 토큰 → 바이트 매핑
CONTROL_TOKEN_TO_BYTES = {
    "[END]": bytes([0x00, 0xFF]),
    "[NEWLINE]": bytes([0x00, 0xFE]),
    "[PAGE]": bytes([0x00, 0xFC]),
    "[WAIT]": bytes([0x00, 0xFA]),
    "[PAUSE]": bytes([0x00, 0xF8]),
    "[CTRL_F0]": bytes([0x00, 0xF0]),
    "[PLAYER_NAME]": bytes([0x05, 0x44]),
    "[LINE_END_08]": bytes([0x08, 0x03]),
    "[LINE_END_09]": bytes([0x09, 0x03]),
    "[LINE_END_0A]": bytes([0x0A, 0x03]),
    "[LINE_END_0B]": bytes([0x0B, 0x03]),
    "[LINE_END_0C]": bytes([0x0C, 0x03]),
    "[LINE_END_0D]": bytes([0x0D, 0x03]),
    "[LINE_END_0E]": bytes([0x0E, 0x03]),
    "[LINE_END_0F]": bytes([0x0F, 0x03]),
    "[LINE_END_10]": bytes([0x10, 0x03]),
    "[LINE_END_11]": bytes([0x11, 0x03]),
    "[LINE_END_12]": bytes([0x12, 0x03]),
    "[LINE_END_13]": bytes([0x13, 0x03]),
    "[LINE_END_19]": bytes([0x19, 0x03]),
}


# ============================================================
# 한글 문자 테이블 관리
# ============================================================
class KoreanCharTable:
    """한글 문자 ↔ 바이트코드 매핑 테이블"""
    
    def __init__(self, table_path=None):
        # 기본 매핑: 한글 문자 → (char_code, page) 바이트 쌍
        self.char_to_bytes = {}
        # 역매핑: (char_code, page) → 한글 문자
        self.bytes_to_char = {}
        
        if table_path and os.path.exists(table_path):
            self.load(table_path)
        else:
            self._build_default_table()
    
    def _build_default_table(self):
        """
        기본 한글 매핑 테이블을 생성합니다.
        
        기존 일본어 1420개 슬롯을 한글로 재배정:
        - Page 0x00 (0x00-0x51): 82슬롯 → 한글 기본 자모/기호
        - Page 0x01 (0x00-0x50): 81슬롯 → 한글 추가
        - Page 0x02+ : 나머지 → 한글 완성형 글자
        
        총 1420슬롯으로 자주 사용되는 한글 완성형 배정
        """
        # 한글 완성형에서 자주 사용되는 글자 (빈도순)
        # 실제 번역에서 사용되는 글자를 우선 배정
        
        # 기본 기호 (Page 0x00의 처음 부분)
        symbols = ' 、。！？…・「」『』（）～♪♡0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        
        # 한글 자주 사용 글자 (빈도 기반)
        # 가나다라... 기본 + 게임 번역에 자주 나오는 글자들
        korean_frequent = (
            '가각간갈감갑강같갖갚개객갤갱거건걸검겁것게겨격견결겸경계고곡곤골곧공과관광괜괴교구국군굴굽궁권귀규균그극근글금급기긴길김'
            '까깝깨꺼꼬꼭꽃꿈꿔끄끊끌끔끝끼나낙난날남납낭낮내낼냄냈너널넘네녀녁년념녕노놀놓농높놔누눈눌눕뉘느늘늑능니닌님닛닝다단닫'
            '달담답당대댄더덕덜덤덥덧도독돈돌돕동두둘둡뒤듣들듬듯등디딩딱딴따딸때떠떡떤떨떻또뚜뛰뜨라락란랄람랑래랜량러럭런럴럼럽'
            '렇레련렬렵령로록론롤롭롯료루룩룰룸류륙률르른를름릇릉리릭린릴림립릿링마막만말많맘맙맛망매맥맨맹머먹먼멀멈멋멍메멘면멸명몇'
            '모목몰몸몹못몽묘무묵문물뭐뭘뭣므미민밀밉밌밍및바박반받발밝밤밥방배백밴뱃버번벌범법벗벤별병보복볼봄봐봤부북분불붉붕붙뷰브'
            '블비빈빌빗빛빠빨빼뻐뽑뿐쁘사삭산살삶삼상새색샌생서석선설섬섭성세센셈셋소속손솔송수숙순숨숫술쉬쉽스슬습승시식신실싫심십싱'
            '싶싸쌀쌍쌓써썩쎄쏘쓰쓸씀씌씩씬씹씻아악안알않앉앎암압앙앞애액앨야약얇양어억언얼얹엄업없엇엉에여역연열엽영예옆오옥온올옮옳'
            '와완왕왜외왼요욕용우운울움웃워원월웨위윗유육윤율으은을음응의이인일읽잃임입잇있잊잖장재잼쟁저적전절점접정제젠젤조족존졸종좋좌'
            '좀주죽준줄줌중쥐즈즐즘증지직진질짐집징짓짝짧째쩔쪽쫓찍찬찮찰참창찾채챙처천철첫청체쳐초촉촌총최추축춘출춤충취츠측츨층치칙친'
            '칠침칭카칸칼캐커컨컬컴케코콜콤쾌쿄쿠크큰클큼키킬타탁탄탈탐탑탓태택탤터턱턴털텀텅테토톡톤통투툴튀튜트특튼틀틈티틱팀팅파판팔'
            '팜팝패팩팬퍼펴편펼평폐포폭폼표푸풀품풍프플피픽필핑하학한할함합항해핵핸행허헌헐험혀현혈협형혜호혹혼홀홍화확환활황회획횟효후훌훔'
            '휘휴흉흐흑흔흘흙흡흥희흰히힘힘'
        )
        
        # 중복 제거
        korean_chars = []
        seen = set()
        for ch in korean_frequent:
            if ch not in seen:
                korean_chars.append(ch)
                seen.add(ch)
        
        # 슬롯 배정
        slot_index = 0
        all_slots = []
        
        # 모든 사용 가능한 슬롯 나열 (페이지별)
        # Page 0x00: 0x00-0x51 (82개)
        for i in range(0x52):
            all_slots.append((i, 0x00))
        # Page 0x01: 0x00-0x50 (81개)
        for i in range(0x51):
            all_slots.append((i, 0x01))
        # Page 0x02-0x3F의 각각 최대 0x42개 (대부분 한자)
        for page in range(0x02, 0x40):
            for i in range(0x42):
                all_slots.append((i, page))
        
        # 기호 배정
        for i, ch in enumerate(symbols):
            if i < len(all_slots):
                char_code, page = all_slots[i]
                self.char_to_bytes[ch] = (char_code, page)
                self.bytes_to_char[(char_code, page)] = ch
        
        # 한글 배정 (기호 뒤부터)
        start_idx = len(symbols)
        for i, ch in enumerate(korean_chars):
            slot_idx = start_idx + i
            if slot_idx < len(all_slots):
                char_code, page = all_slots[slot_idx]
                self.char_to_bytes[ch] = (char_code, page)
                self.bytes_to_char[(char_code, page)] = ch
        
        print(f"  기본 한글 테이블 생성: {len(self.char_to_bytes)}개 문자 매핑")
    
    def load(self, path):
        """JSON 파일에서 매핑 테이블 로드"""
        with open(path, 'r', encoding='utf-8') as f:
            table_data = json.load(f)
        
        for char, mapping in table_data.items():
            if isinstance(mapping, list) and len(mapping) == 2:
                char_code, page = mapping
                self.char_to_bytes[char] = (char_code, page)
                self.bytes_to_char[(char_code, page)] = char
            elif isinstance(mapping, dict):
                char_code = mapping['char_code']
                page = mapping['page']
                self.char_to_bytes[char] = (char_code, page)
                self.bytes_to_char[(char_code, page)] = char
        
        print(f"  한글 테이블 로드: {len(self.char_to_bytes)}개 문자 매핑")
    
    def save(self, path):
        """매핑 테이블을 JSON으로 저장"""
        table_data = {}
        for char, (char_code, page) in sorted(self.char_to_bytes.items()):
            table_data[char] = {
                'char_code': char_code,
                'page': page,
                'hex': f"{char_code:02X} {page:02X}"
            }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(table_data, f, ensure_ascii=False, indent=2)
        
        print(f"  한글 테이블 저장: {path}")
    
    def encode_char(self, char):
        """한글 문자를 바이트 쌍으로 인코딩"""
        if char in self.char_to_bytes:
            char_code, page = self.char_to_bytes[char]
            return bytes([char_code, page])
        else:
            # 매핑되지 않은 문자는 공백으로 대체
            if ' ' in self.char_to_bytes:
                char_code, page = self.char_to_bytes[' ']
                return bytes([char_code, page])
            return bytes([0x00, 0x00])  # 폴백


# ============================================================
# 번역 텍스트 인코딩
# ============================================================
def encode_translated_text(text, char_table):
    """
    번역된 텍스트 문자열을 ROM 바이트로 인코딩합니다.
    
    입력 형식:
        일반 문자: 한글/영문/숫자/기호
        제어코드: [END], [NEWLINE], [PAGE], [WAIT], [PAUSE], [PLAYER_NAME]
        줄 끝: [LINE_END_10], [LINE_END_11], etc.
    
    Returns:
        bytes: 인코딩된 바이트 데이터
    """
    result = bytearray()
    i = 0
    
    while i < len(text):
        # 제어코드 토큰 확인
        if text[i] == '[':
            # 토큰 끝 찾기
            end = text.find(']', i)
            if end != -1:
                token = text[i:end + 1]
                if token in CONTROL_TOKEN_TO_BYTES:
                    result.extend(CONTROL_TOKEN_TO_BYTES[token])
                    i = end + 1
                    continue
                else:
                    # 알 수 없는 토큰 → hex 코드로 해석 시도
                    # 형식: [XX:YY] 또는 [XX]
                    inner = token[1:-1]
                    if ':' in inner:
                        parts = inner.split(':')
                        try:
                            b1 = int(parts[0], 16)
                            b2 = int(parts[1], 16)
                            result.extend([b1, b2])
                            i = end + 1
                            continue
                        except ValueError:
                            pass
            
            # 토큰이 아닌 경우 일반 문자로 처리
            result.extend(char_table.encode_char(text[i]))
            i += 1
        
        # 줄바꿈 문자
        elif text[i] == '\n':
            result.extend(CONTROL_TOKEN_TO_BYTES["[NEWLINE]"])
            i += 1
        
        # 일반 문자
        else:
            result.extend(char_table.encode_char(text[i]))
            i += 1
    
    return bytes(result)


# ============================================================
# ROM 텍스트 삽입
# ============================================================
def insert_text_into_rom(rom_data, translated_dir, char_table):
    """
    번역된 텍스트를 ROM에 삽입합니다.
    
    전략:
    1. 각 텍스트 뱅크를 처음부터 다시 작성
    2. 번역된 텍스트 블록을 순서대로 배치
    3. 스크립트 뱅크의 포인터를 새 주소로 업데이트
    
    Returns:
        bytearray: 수정된 ROM 데이터
    """
    modified_rom = bytearray(rom_data)
    
    # 각 텍스트 뱅크 처리
    stats = {
        'translated': 0,
        'unchanged': 0,
        'overflow': 0,
        'total_banks': 0,
    }
    
    for bank_num in TEXT_BANKS:
        json_path = os.path.join(translated_dir, f"bank_{bank_num:03d}.json")
        
        if not os.path.exists(json_path):
            continue
        
        with open(json_path, 'r', encoding='utf-8') as f:
            blocks = json.load(f)
        
        # 번역된 블록이 있는지 확인
        has_translation = any(b.get('translation', '').strip() for b in blocks)
        if not has_translation:
            stats['unchanged'] += 1
            continue
        
        stats['total_banks'] += 1
        
        # 새 텍스트 뱅크 데이터 구성
        bank_base = bank_num * BANK_SIZE
        new_bank_data = bytearray()
        
        # 첫 바이트: 뱅크 번호
        new_bank_data.append(bank_num & 0xFF)
        
        # 원본 오프셋 → 새 오프셋 매핑
        offset_map = {}  # {원본_ROM_offset: 새_뱅크내_주소}
        
        for block in blocks:
            original_offset = int(block['rom_offset'], 16)
            translation = block.get('translation', '').strip()
            
            # 현재 뱅크 내 주소 계산
            new_addr_in_bank = len(new_bank_data)
            new_gbc_addr = 0x4000 + new_addr_in_bank  # GBC 주소 공간
            
            # 오프셋 매핑 저장
            offset_map[original_offset] = new_gbc_addr
            
            if translation:
                # 번역된 텍스트 인코딩
                encoded = encode_translated_text(translation, char_table)
                new_bank_data.extend(encoded)
                stats['translated'] += 1
            else:
                # 원본 유지 (raw hex에서 복원)
                raw_hex = block.get('raw_hex', '')
                if raw_hex:
                    original_bytes = bytes.fromhex(raw_hex)
                    new_bank_data.extend(original_bytes)
                stats['unchanged'] += 1
        
        # 뱅크 크기 체크
        if len(new_bank_data) > BANK_SIZE:
            overflow = len(new_bank_data) - BANK_SIZE
            print(f"  ⚠️  Bank {bank_num}: 오버플로우! ({overflow} bytes 초과)")
            print(f"      원본: {BANK_SIZE} bytes, 번역 후: {len(new_bank_data)} bytes")
            stats['overflow'] += 1
            # 뱅크 크기로 자르기 (데이터 손실 경고)
            new_bank_data = new_bank_data[:BANK_SIZE]
        else:
            # 나머지를 0x00으로 패딩
            padding_needed = BANK_SIZE - len(new_bank_data)
            new_bank_data.extend(bytes(padding_needed))
        
        # ROM에 새 뱅크 데이터 쓰기
        modified_rom[bank_base:bank_base + BANK_SIZE] = new_bank_data
        
        # 스크립트 뱅크의 포인터 업데이트
        update_script_pointers(modified_rom, bank_num, offset_map)
        
        print(f"  Bank {bank_num}: {len(new_bank_data)} bytes 기록됨 "
              f"(여유: {BANK_SIZE - len(new_bank_data)} bytes)")
    
    return bytes(modified_rom), stats


def update_script_pointers(rom_data, text_bank, offset_map):
    """
    스크립트 뱅크의 텍스트 포인터를 업데이트합니다.
    
    패턴: 19 [addr_lo] [addr_hi] [text_bank] 1B
    """
    for script_bank in SCRIPT_BANKS:
        base = script_bank * BANK_SIZE
        
        i = 0
        while i < BANK_SIZE - 4:
            # 텍스트 참조 패턴 찾기
            if (rom_data[base + i] == 0x19 and
                rom_data[base + i + 3] == text_bank and
                rom_data[base + i + 4] == 0x1B):
                
                addr_lo = rom_data[base + i + 1]
                addr_hi = rom_data[base + i + 2]
                old_addr = addr_lo | (addr_hi << 8)
                
                if 0x4000 <= old_addr <= 0x7FFF:
                    # 원본 ROM 오프셋 계산
                    original_rom_offset = text_bank * BANK_SIZE + (old_addr - 0x4000)
                    
                    # 새 주소 찾기
                    if original_rom_offset in offset_map:
                        new_addr = offset_map[original_rom_offset]
                        rom_data[base + i + 1] = new_addr & 0xFF
                        rom_data[base + i + 2] = (new_addr >> 8) & 0xFF
            
            i += 1


# ============================================================
# ROM 체크섬 수정
# ============================================================
def fix_checksum(rom_data):
    """GBC ROM 헤더 체크섬을 재계산합니다."""
    rom = bytearray(rom_data)
    
    # 헤더 체크섬 (0x014D)
    checksum = 0
    for i in range(0x0134, 0x014D):
        checksum = (checksum - rom[i] - 1) & 0xFF
    rom[0x014D] = checksum
    
    # 글로벌 체크섬 (0x014E-0x014F)
    rom[0x014E] = 0
    rom[0x014F] = 0
    global_sum = 0
    for byte in rom:
        global_sum = (global_sum + byte) & 0xFFFF
    rom[0x014E] = (global_sum >> 8) & 0xFF
    rom[0x014F] = global_sum & 0xFF
    
    return bytes(rom)


# ============================================================
# 메인 삽입 함수
# ============================================================
def insert_translation(rom_path, translated_dir, output_path):
    """메인 한글화 삽입 프로세스"""
    
    print("=" * 60)
    print("  Pia Carrot he Youkoso!! 2.2 - 한글 텍스트 삽입기")
    print("=" * 60)
    print()
    
    # ROM 로드
    print(f"[1/5] ROM 로딩: {rom_path}")
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    print(f"  ROM 크기: {len(rom_data):,} bytes")
    print()
    
    # 한글 문자 테이블 로드/생성
    print("[2/5] 한글 문자 테이블 준비...")
    table_path = os.path.join(translated_dir, "korean_table.json")
    char_table = KoreanCharTable(table_path if os.path.exists(table_path) else None)
    
    # 테이블이 새로 생성된 경우 저장
    if not os.path.exists(table_path):
        os.makedirs(translated_dir, exist_ok=True)
        char_table.save(table_path)
    print()
    
    # 번역 파일 확인
    print("[3/5] 번역 파일 확인...")
    translated_count = 0
    total_blocks = 0
    for bank_num in TEXT_BANKS:
        json_path = os.path.join(translated_dir, f"bank_{bank_num:03d}.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                blocks = json.load(f)
            total_blocks += len(blocks)
            translated_count += sum(1 for b in blocks if b.get('translation', '').strip())
    
    print(f"  총 텍스트 블록: {total_blocks}")
    print(f"  번역된 블록: {translated_count}")
    print(f"  번역률: {translated_count/max(total_blocks,1)*100:.1f}%")
    
    if translated_count == 0:
        print()
        print("⚠️  번역된 텍스트가 없습니다!")
        print("   1. dump/ 디렉토리의 bank_XXX.json 파일을 복사하여")
        print("   2. translated/ 디렉토리에 넣고")
        print("   3. 각 블록의 'translation' 필드에 한국어 번역을 입력하세요")
        print()
        print("   예시:")
        print('   {"id": "B152_0001", ..., "translation": "혹시 모르니까[LINE_END_10][NEWLINE]제대로 확인해 봐야지[LINE_END_11][END]"}')
        return
    
    print()
    
    # 텍스트 삽입
    print("[4/5] 텍스트 삽입 중...")
    modified_rom, stats = insert_text_into_rom(rom_data, translated_dir, char_table)
    print()
    print(f"  번역 삽입: {stats['translated']}개 블록")
    print(f"  원본 유지: {stats['unchanged']}개 블록")
    if stats['overflow'] > 0:
        print(f"  ⚠️  오버플로우: {stats['overflow']}개 뱅크 (일부 데이터 잘림)")
    print()
    
    # 체크섬 수정
    print("[5/5] 체크섬 수정 및 저장...")
    final_rom = fix_checksum(modified_rom)
    
    # 출력 파일 저장
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(final_rom)
    
    print(f"  출력: {output_path}")
    print(f"  크기: {len(final_rom):,} bytes")
    print()
    print("=" * 60)
    print("  한글화 ROM 생성 완료!")
    print("=" * 60)


# ============================================================
# 유틸리티: 샘플 번역 파일 생성
# ============================================================
def create_sample_translation(dump_dir, output_dir):
    """
    dump 디렉토리의 파일을 기반으로 샘플 번역 파일을 생성합니다.
    처음 몇 블록에 예시 번역을 넣어줍니다.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Bank 152의 처음 몇 블록을 샘플로
    src_path = os.path.join(dump_dir, "bank_152.json")
    if not os.path.exists(src_path):
        print(f"오류: {src_path} 파일이 없습니다. 먼저 text_dumper.py를 실행하세요.")
        return
    
    with open(src_path, 'r', encoding='utf-8') as f:
        blocks = json.load(f)
    
    # 처음 5개 블록에 샘플 번역 추가
    sample_translations = [
        "이번 여름 방학은[LINE_END_10]아르바이트를 하자[LINE_END_11][END]",
        "어쩌면 좋은 만남이[LINE_END_10]있을지도 몰라[LINE_END_11][END]",
        "[PLAYER_NAME][PLAYER_NAME]아아아아이[LINE_END_11][END]",
        "네[LINE_END_10]알겠습니다[PLAYER_NAME][PLAYER_NAME][LINE_END_11][END]",
        "그럼 확인해볼게[LINE_END_10]이번 여름 방학은[LINE_END_11][NEWLINE][WAIT]알겠어[LINE_END_11][END]",
    ]
    
    for i, trans in enumerate(sample_translations):
        if i < len(blocks):
            blocks[i]['translation'] = trans
    
    dst_path = os.path.join(output_dir, "bank_152.json")
    with open(dst_path, 'w', encoding='utf-8') as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)
    
    print(f"샘플 번역 파일 생성: {dst_path}")
    print(f"  {min(len(sample_translations), len(blocks))}개 블록에 예시 번역 추가됨")


# ============================================================
# 진입점
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print()
        print("추가 명령:")
        print("  python text_inserter.py --sample <dump_dir> <output_dir>")
        print("    → 샘플 번역 파일 생성")
        print()
        sys.exit(1)
    
    if sys.argv[1] == '--sample':
        dump_dir = sys.argv[2] if len(sys.argv) > 2 else './dump'
        output_dir = sys.argv[3] if len(sys.argv) > 3 else './translated'
        create_sample_translation(dump_dir, output_dir)
    else:
        rom_path = sys.argv[1]
        translated_dir = sys.argv[2] if len(sys.argv) > 2 else './translated'
        output_path = sys.argv[3] if len(sys.argv) > 3 else './output_kr.gbc'
        
        if not os.path.exists(rom_path):
            print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
            sys.exit(1)
        
        insert_translation(rom_path, translated_dir, output_path)
