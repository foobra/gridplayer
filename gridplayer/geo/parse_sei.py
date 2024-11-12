import json
from typing import List, Tuple
import urllib.parse
import urllib.request
import http.client

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FOV:
    id: int
    x: int
    y: int
    width: int
    height: int

@dataclass
class SEI:
    is_valid: bool
    stitching_layout: int
    camera_number: int
    camera_model: int
    camera_resolution_x: int
    camera_resolution_y: int
    video_resolution_x: int
    video_resolution_y: int
    texture_padding_size: int
    background_texture_flag: int
    background_depth_flag: int
    arrangement_flag: int
    horizontal_half_fov: int
    fov_array: List[FOV]

@dataclass
class VideoData:
    sei: SEI

# 用于裁剪的 VideoCrop 数据类
@dataclass
class VideoCrop:
    left: int
    top: int
    right: int
    bottom: int



MAX_UVLC_LEADING_ZEROS = 20
UVLC_ERROR = -99999


class BitReader:
    def __init__(self, buffer):
        self.data = buffer
        self.bytes_remaining = len(buffer)
        self.byte_pos = 0
        self.bit_pos = 0
        self.nextbits = 0
        self.nextbits_cnt = 0
        self.refill()

    def refill(self):
        while self.nextbits_cnt <= 56 and self.bytes_remaining > 0:
            # 读取下一个字节并将其加入到 nextbits
            new_byte = self.data[self.byte_pos]
            self.byte_pos += 1
            self.bytes_remaining -= 1

            self.nextbits = (self.nextbits << 8) | new_byte
            self.nextbits_cnt += 8

    def get_bits(self, n):
        # 确保我们有足够的比特
        if self.nextbits_cnt < n:
            self.refill()

        # 从最高位开始读取 n 位
        val = (self.nextbits >> (self.nextbits_cnt - n)) & ((1 << n) - 1)
        self.nextbits_cnt -= n

        # 清除已经读取的比特
        self.nextbits &= (1 << self.nextbits_cnt) - 1
        return val

    def peek_bits(self, n):
        if self.nextbits_cnt < n:
            self.refill()
        return (self.nextbits >> (self.nextbits_cnt - n)) & ((1 << n) - 1)

    def skip_bits(self, n):
        if self.nextbits_cnt < n:
            self.refill()
        self.nextbits_cnt -= n
        self.nextbits &= (1 << self.nextbits_cnt) - 1

    def skip_to_byte_boundary(self):
        nskip = self.nextbits_cnt % 8
        if nskip > 0:
            self.skip_bits(nskip)

    def prepare_for_CABAC(self):
        self.skip_to_byte_boundary()
        rewind = self.nextbits_cnt // 8
        self.byte_pos -= rewind
        self.bytes_remaining += rewind
        self.nextbits = 0
        self.nextbits_cnt = 0

    def get_uvlc(self):
        num_zeros = 0

        while self.get_bits(1) == 0:
            num_zeros += 1
            if num_zeros > MAX_UVLC_LEADING_ZEROS:
                return UVLC_ERROR

        offset = self.get_bits(num_zeros) if num_zeros > 0 else 0
        value = offset + (1 << num_zeros) - 1 if num_zeros > 0 else 0
        return value

    def get_svlc(self):
        v = self.get_uvlc()
        if v == 0 or v == UVLC_ERROR:
            return v
        negative = (v & 1) == 0
        return -(v // 2) if negative else (v + 1) // 2

    def check_rbsp_trailing_bits(self):
        stop_bit = self.get_bits(1)
        if stop_bit != 1:
            return False
        while self.nextbits_cnt > 0 or self.bytes_remaining > 0:
            if self.get_bits(1) != 0:
                return False
        return True

class FieldOfViewInfo:
    def __init__(self, id: int, x: int, y: int, width: int, height: int):
        self.id = id
        self.x = x
        self.y = y
        self.width = width
        self.height = height

class SEI_6DOF:
    class StitchingLayout:
        DecodedFrameWithTextureAndDepth_0 = 0
        DecodedFrameWithTextureAndSeparateDepth_1 = 1
        DecodedFrameWithTextureOnlySeparateDepth_2 = 2
        Reserved = 3

    class CameraModel:
        PinholeModel_0 = 0
        FisheyeModel_1 = 1
        Reserved_2 = 2

    class BackgroundTextureFlag:
        NoBackgroundTexture_0 = 0
        HasBackgroundTexture_1 = 1

    class ArrangementMode:
        DisallowSwitchToFirstView_0 = 0
        AllowSwitchToFirstView_1 = 1

    def __init__(self):
        self.uuid_string = ""
        self.stitching_layout = None
        self.camera_number = 0
        self.camera_model = None
        self.camera_resolution_x = 0
        self.camera_resolution_y = 0
        self.video_resolution_x = 0
        self.video_resolution_y = 0
        self.texture_padding_size = 0
        self.background_texture_flag = 0
        self.background_depth_flag = None
        self.arrangement_flag = None
        self.horizontal_half_fov = 0
        self.texture_top_left_x = []
        self.texture_top_left_y = []
        self.texture_bottom_right_x = []
        self.texture_bottom_right_y = []

    def is_valid(self):
        return self.uuid_string == "_6dof_extension_"

def convert_to_json(sei: SEI_6DOF, fov_array: List[FieldOfViewInfo]) -> dict:
    sei_json = {
        "sei": {
            "is_valid": sei.is_valid(),
            "stitching_layout": sei.stitching_layout,
            "camera_number": sei.camera_number,
            "camera_model": sei.camera_model,
            "camera_resolution_x": sei.camera_resolution_x,
            "camera_resolution_y": sei.camera_resolution_y,
            "video_resolution_x": sei.video_resolution_x,
            "video_resolution_y": sei.video_resolution_y,
            "texture_padding_size": sei.texture_padding_size,
            "background_texture_flag": sei.background_texture_flag,
            "background_depth_flag": sei.background_depth_flag,
            "arrangement_flag": sei.arrangement_flag,
            "horizontal_half_fov": sei.horizontal_half_fov
        },
        "fov_array": [
            {
                "id": fov.id,
                "x": fov.x,
                "y": fov.y,
                "width": fov.width,
                "height": fov.height
            } for fov in fov_array
        ]
    }
    return sei_json

def read_sei_6dof(reader: BitReader) -> Tuple[SEI_6DOF, List[FieldOfViewInfo]]:
    sei = SEI_6DOF()
    fov_info_array = []

    for _ in range(16):
        uuid_char = chr(reader.get_bits(8))
        sei.uuid_string += uuid_char

    if not sei.is_valid():
        return None, []

    sei.stitching_layout = reader.get_bits(2)
    sei.camera_number = reader.get_bits(16)
    sei.camera_model = reader.get_bits(2)
    reader.get_bits(1)  # marker_bit

    sei.camera_resolution_x = reader.get_bits(16)
    reader.get_bits(1)  # marker_bit
    sei.camera_resolution_y = reader.get_bits(16)
    reader.get_bits(1)  # marker_bit

    sei.video_resolution_x = reader.get_bits(16)
    reader.get_bits(1)  # marker_bit
    sei.video_resolution_y = reader.get_bits(16)
    reader.get_bits(1)  # marker_bit

    sei.texture_padding_size = reader.get_bits(8)
    sei.background_texture_flag = reader.get_bits(1)
    sei.background_depth_flag = reader.get_bits(1)
    reader.get_bits(1)  # marker_bit

    sei.arrangement_flag = reader.get_bits(1)
    sei.horizontal_half_fov = reader.get_bits(8)
    reader.get_bits(3)  # reserved_bits

    for _ in range(sei.camera_number):
        top_left_x = reader.get_bits(16)
        reader.get_bits(1)  # marker_bit
        top_left_y = reader.get_bits(16)
        reader.get_bits(1)  # marker_bit
        bottom_right_x = reader.get_bits(16)
        reader.get_bits(1)  # marker_bit
        bottom_right_y = reader.get_bits(16)
        reader.get_bits(1)  # marker_bit

        reader.get_bits(4)  # reserved_bits

        fov_info_array.append(FieldOfViewInfo(len(fov_info_array)+1, top_left_x, top_left_y, bottom_right_x - top_left_x, bottom_right_y-top_left_y))

    return sei, fov_info_array

VIDEO_PID = 0x100  # 根据实际情况设定 PID
TS_PACKET_SIZE = 188

def extract_h265_nal_from_ts(ts_stream):
    nal_data = bytearray()
    start_of_nal = False

    for i in range(0, len(ts_stream), TS_PACKET_SIZE):
        packet = ts_stream[i:i + TS_PACKET_SIZE]

        # 检查同步字节
        if packet[0] != 0x47:
            print("Sync byte not found!")
            continue

        # 解析 PID
        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        if pid != VIDEO_PID:
            continue

        # 检查有效载荷单元起始指示符
        payload_unit_start = packet[1] & 0x40

        # 跳过 TS 头，计算有效载荷起始位置
        payload_start = 4
        if packet[3] & 0x20:  # 适配域控制位
            payload_start += 1 + packet[4]

        if payload_start >= TS_PACKET_SIZE:
            continue

        # 如果是 PES 包的起始位置
        if payload_unit_start:
            if start_of_nal:
                # 遇到新 NAL 单元，添加 0x000001 起始码
                nal_data += b'\x00\x00\x01'
            start_of_nal = True

            # 跳过 PES 头
            if packet[payload_start:payload_start+3] == b'\x00\x00\x01':
                payload_start += 9 + (packet[payload_start + 8] & 0x0F)

        # 将有效载荷数据添加到 NAL 数据中
        nal_data += packet[payload_start:]

    return bytes(nal_data)


def find_6dof_extension_in_nal(nal_data):
    extension_string = b"_6dof_extension_"
    idx = nal_data.find(extension_string)
    if idx == -1:
        return None
    return nal_data[idx:]

def process_ts_file(data):
    # 提取 H.265 NAL 单元
    nal_data = extract_h265_nal_from_ts(data)

    if not nal_data:
        print("Failed to extract NAL data")
        return None

    # 查找 _6dof_extension_ NAL 数据
    new_nal_data = find_6dof_extension_in_nal(nal_data)

    if not new_nal_data:
        print("Failed to find 6DOF extension")
        return None

    # 初始化 bitreader 和解析 SEI 数据
    reader = BitReader(new_nal_data)  # Create BitReader with NAL data
    sei_c, fov_info_array = read_sei_6dof(reader)  # Pass the BitReader object

    if not sei_c or fov_info_array is None:
        print("Failed to read SEI data")
        return None

    # 转换为 JSON
    result = convert_to_json(sei_c, fov_info_array)

    # 转换 JSON 为字符串并返回
    json_str = json.dumps(result, indent=4)
    return json_str


def read_ts_file(file_path, read_size=2048):
    try:
        with open(file_path, 'rb') as ts_file:
            ts_stream = ts_file.read(read_size)
            if len(ts_stream) < read_size:
                print(f"Failed to read {read_size} bytes, only {len(ts_stream)} bytes read")
                return None
            return ts_stream
    except IOError:
        print("Failed to open TS file")
        return None


def download_first_ts_segment(url):
    # 下载 m3u8 文件内容
    with urllib.request.urlopen(url) as response:
        m3u8_content = response.read().decode("utf-8")

    # 解析 m3u8 文件，找到第一个 ts 文件的 URL
    ts_url = None
    for line in m3u8_content.splitlines():
        if line and not line.startswith("#"):
            ts_url = line
            break

    if ts_url is None:
        raise ValueError("未找到有效的 TS 文件链接")

    # 如果 ts_url 是相对路径，则将其转为绝对路径
    ts_url = urllib.parse.urljoin(url, ts_url)
    parsed_ts_url = urllib.parse.urlparse(ts_url)

    # 使用 http.client 请求 TS 文件的前 2048 字节
    conn = http.client.HTTPConnection(parsed_ts_url.netloc)
    conn.request("GET", parsed_ts_url.path + ("?" + parsed_ts_url.query if parsed_ts_url.query else ""), headers={"Range": "bytes=0-2047"})

    # 获取响应并读取内容
    response = conn.getresponse()
    if response.status != 206:  # 206 是部分内容状态码
        raise ValueError("未成功获取 TS 文件的部分内容")

    data = response.read()
    conn.close()

    return data


def parse_video_data(json_data: dict) -> VideoData:
    fov_array = [FOV(**fov) for fov in json_data["fov_array"]]
    sei = SEI(**json_data["sei"], fov_array=fov_array)
    return VideoData(sei=sei)

# def main():
#     # file_path = "/Users/jtang/Documents/Projects/Migu/MGYX/hls/202406171557-000-228.ts"


#     url = "http://127.0.0.1:8080/index.m3u8"  # 替换为实际的 m3u8 地址
#     ts_stream = download_first_ts_segment(url)

#     # 读取TS文件前2048字节
#     # ts_stream = read_ts_file(file_path)
#     if ts_stream is None:
#         return -1

#     # 处理TS文件并提取6DOF扩展信息的JSON
#     json_str = process_ts_file(ts_stream)

#     if json_str:
#         print(json_str)
#     else:
#         print("Failed to process TS file.")

# if __name__ == "__main__":
#     main()
