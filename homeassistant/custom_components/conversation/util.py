"""Util for Conversation."""
import re
import string
import random
import json, os, aiohttp, uuid
from homeassistant.helpers import template, entity_registry, area_registry

def create_matcher(utterance):
    """Create a regex that matches the utterance."""
    # Split utterance into parts that are type: NORMAL, GROUP or OPTIONAL
    # Pattern matches (GROUP|OPTIONAL): Change light to [the color] {name}
    parts = re.split(r"({\w+}|\[[\w\s]+\] *)", utterance)
    # Pattern to extract name from GROUP part. Matches {name}
    group_matcher = re.compile(r"{(\w+)}")
    # Pattern to extract text from OPTIONAL part. Matches [the color]
    optional_matcher = re.compile(r"\[([\w ]+)\] *")

    pattern = ["^"]
    for part in parts:
        group_match = group_matcher.match(part)
        optional_match = optional_matcher.match(part)

        # Normal part
        if group_match is None and optional_match is None:
            pattern.append(part)
            continue

        # Group part
        if group_match is not None:
            pattern.append(r"(?P<{}>[\w ]+?)\s*".format(group_match.groups()[0]))

        # Optional part
        elif optional_match is not None:
            pattern.append(r"(?:{} *)?".format(optional_match.groups()[0]))

    pattern.append("$")
    return re.compile("".join(pattern), re.I)
# 获取本机MAC地址
def get_mac_address(): 
    mac=uuid.UUID(int = uuid.getnode()).hex[-12:] 
    return ":".join([mac[e:e+2] for e in range(0,11,2)])
########################################## 常量
VERSION = '1.3.2'
DOMAIN = "conversation"
DATA_AGENT = "conversation_agent"
DATA_CONFIG = "conversation_config"
MAC_ADDRESS = get_mac_address().replace(':','').lower()
XIAOAI_API = f"/conversation-xiaoai-{MAC_ADDRESS}"
XUNFEI_API = f"/conversation-xunfei-{MAC_ADDRESS}"
VIDEO_API = '/conversation-video'
########################################## 查询实体
def isMatchDomain(type, domain):
    return type is None or (isinstance(type, list) and type.count(domain) == 1) or (isinstance(type, str) and type == domain)

async def find_entity(hass, name, type = None):
    # 遍历所有实体
    states = hass.states.async_all()
    for state in states:
        entity_id = state.entity_id
        domain = state.domain
        attributes = state.attributes
        friendly_name = attributes.get('friendly_name')
        # 查询对应的设备名称
        if friendly_name is not None and friendly_name.lower() == name.lower():
            # 指定类型
            if isMatchDomain(type, domain):
                return state
    # 如果没有匹配到实体，则开始从区域里查找
    arr = name.split('的', 1)
    if len(arr) == 2:
        area_name = arr[0]
        device_name = arr[1]
        # 获取所有区域
        area = await area_registry.async_get_registry(hass)
        area_list = area.async_list_areas()
        _list = list(filter(lambda item: item.name == area_name, area_list))
        if(len(_list) > 0):
            area_id = _list[0].id
            entity = await entity_registry.async_get_registry(hass)
            entity_list = entity_registry.async_entries_for_area(entity, area_id)
            # 有设备才处理
            if len(entity_list) > 0:
                # 查找完整设备
                _list = list(filter(lambda item: item.name == device_name or item.original_name == device_name, entity_list))
                if(len(_list) > 0):
                    # print(_list)
                    item = _list[0]
                    state = hass.states.get(item.entity_id)
                    if isMatchDomain(type, state.domain):
                        return state
                # 如果直接说了灯或开关
                if device_name == '灯':
                    # 如果只有一个设备
                    if len(entity_list) == 1:
                        item = entity_list[0]
                        state = hass.states.get(item.entity_id)
                        if isMatchDomain(type, state.domain):
                            return state
                    else:
                        # 取第一个含有灯字的设备（这里可以通过其他属性来判断，以后再考虑）
                        for item in entity_list:
                            state = hass.states.get(item.entity_id)
                            friendly_name = state.attributes.get('friendly_name')
                            if '灯' in friendly_name and isMatchDomain(type, state.domain):
                                return state

########################################## 去掉前后标点符号
def trim_char(text):
    return text.strip(' 。，、＇：∶；?‘’“”〝〞ˆˇ﹕︰﹔﹖﹑·¨….¸;！´？！～—ˉ｜‖＂〃｀@﹫¡¿﹏﹋﹌︴々﹟#﹩$﹠&﹪%*﹡﹢﹦﹤‐￣¯―﹨ˆ˜﹍﹎+=<­­＿_-\ˇ~﹉﹊（）〈〉‹›﹛﹜『』〖〗［］《》〔〕{}「」【】︵︷︿︹︽_﹁﹃︻︶︸﹀︺︾ˉ﹂﹄︼')
########################################## 汉字转数字
common_used_numerals_tmp ={'零':0, '一':1, '二':2, '两':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10, '百':100, '千':1000, '万':10000, '亿':100000000}
common_used_numerals = {}
for key in common_used_numerals_tmp:
  common_used_numerals[key.encode('cp936').decode('cp936')] = common_used_numerals_tmp[key]

def chinese2digits(uchars_chinese):
    try:
        uchars_chinese = uchars_chinese.encode('cp936').decode('cp936')
        total = 0
        r = 1              #表示单位：个十百千...
        for i in range(len(uchars_chinese) - 1, -1, -1):
            val = common_used_numerals.get(uchars_chinese[i])
            if val >= 10 and i == 0:  #应对 十三 十四 十*之类
                if val > r:
                    r = val
                    total = total + val
                else:
                    r = r * val
                #total =total + r * x
            elif val >= 10:
                if val > r:
                    r = val
                else:
                    r = r * val
            else:
                total = total + r * val
        return total
    except Exception as ex:
        return None

# 判断是否数字
def is_number(s):
    result = re.match(r'\d+', s)
    if result:
        return True
    else:
        return False

def format_number(num):
    if is_number(num) == False:
        num = chinese2digits(num)
    return float(num)

########################################## 颜色调整
def matcher_light_color(text):
    matchObj = re.match(r'(.+)(调成|设为|设置为|调为)(.*)色', text)
    if matchObj is not None:
        name = trim_char(matchObj.group(1)) 
        color = matchObj.group(3)
        colorObj = {
            '红': 'red',
            '橙': 'orange',
            '黄': 'yellow',
            '绿': 'green',
            '青': 'teal',
            '蓝': 'blue',
            '紫': 'purple',
            '粉': 'pink',
            '白': 'white',
            '紫红': 'fuchsia',
            '橄榄': 'olive'
        }
        # 设备
        if name[0:1] == '把':
            name = name[1:]
        # 随机颜色
        if color == '随机':
            color = random.choice(list(colorObj))
        # 固定颜色
        if color in colorObj:
            return (name, colorObj[color], color)

########################################## 模式调整
def matcher_light_mode(text):
    matchObj = re.match(r'(.+)(调成|设为|设置为|调为)(.*)模式', text)
    if matchObj is not None:
        name = trim_char(matchObj.group(1)) 
        mode = matchObj.group(3)
        modeObj = {
            '随机': 'Random',
            '闪光': 'Strobe',
            '闪烁': 'Twinkle',
            '顔色闪烁': 'Random Twinkle',
            '彩虹': 'Rainbow',
            '跑马灯': 'Color Wipe',
            '扫描': 'Scan',
            '烟火': 'Fireworks'
        }
        # 设备
        if name[0:1] == '把':
            name = name[1:]
        # 固定颜色
        if mode in modeObj:
            return (name, modeObj[mode], mode)

########################################## 亮度调整
def matcher_brightness(text):
    matchObj = re.match(r'(.+)亮度(调成|调到|调为|设为)(.*)', text)
    if matchObj is not None:
        name = trim_char(matchObj.group(1)) 
        brightness = matchObj.group(3)
        # print(brightness)
        # 设备
        if name[0:1] == '把':
            name = name[1:]
        if name[-1] == '的':
            name = name[:-1]
        # 判断是否数字，然后转意
        if re.match(r'^\d+$', brightness):
            brightness = int(brightness)
            if brightness > 100:
                brightness = 100
        # 亮度
        elif brightness == '最亮':
            brightness = 100
        elif brightness == '最暗':
            brightness = 1
        else:
            brightness = chinese2digits(brightness)
            if brightness is None:
                brightness = 0
        # 如果亮度大于0，返回设备名称和亮度值
        if brightness > 0:
            return (name, brightness)

########################################## 执行脚本
def matcher_script(text):
    matchObj = re.match(r'执行脚本(.*)', text)
    if matchObj is not None:
        return matchObj.group(1)

########################################## (执行|触发|打开|关闭)自动化
def matcher_automation(text):
    matchObj = re.match(r'(执行|触发|打开|关闭)自动化(.*)', text)
    if matchObj is not None:
        return (matchObj.group(1), trim_char(matchObj.group(2)))

########################################## (执行|触发|打开|关闭)开关
def matcher_switch(text):
    matchObj = re.match(r'.*((打开|开启|启动|关闭|关掉|关上|切换)(.+))', text)
    if matchObj is not None:
        service_type = ''
        intent_type = ''
        action = matchObj.group(2)
        if ['打开', '开启', '启动'].count(action) == 1:
            service_type = 'turn_on'
            intent_type = 'HassTurnOn'
        elif ['关闭', '关掉', '关上'].count(action) == 1:
            service_type = 'turn_off'
            intent_type = 'HassTurnOff'
        elif action == '切换':
            service_type = 'toggle'
            intent_type = 'HassToggle'
        
        if service_type != '' and intent_type != '':
            return (trim_char(matchObj.group(3)), service_type, intent_type, action)

########################################## (打开|关闭)设备(打开|关闭)设备
def matcher_on_off(text):
    matchObj = re.match(r'(打开|关闭)(.+)(打开|关闭)(.+)', text)
    if matchObj is not None:
        name1 = matchObj.group(2)
        name2 = matchObj.group(4)
        if name1 is not None and name2 is not None:
            type1 = matchObj.group(1) == '打开' and 'turn_on' or 'turn_off'
            type2 = matchObj.group(3) == '打开' and 'turn_on' or 'turn_off'
            _list1 = list(filter(lambda x: x != '', name1.split('和')))
            _list2 = list(filter(lambda x: x != '', name2.split('和')))
            return ((type1, _list1), (type2, _list2))

########################################## 查看设备状态
def matcher_query_state(text):
    matchObj = re.match(r'(查看|查询)(.*)的状态', text)
    if matchObj is not None:
        return trim_char(matchObj.group(2))

    matchObj = re.match(r'(查看|查询)(.*)', text)
    if matchObj is not None:
        return trim_char(matchObj.group(2))
    
    matchObj = re.match(r'(.*)的状态', text)
    if matchObj is not None:
        return trim_char(matchObj.group(1))

########################################## 看电视
# 视频源地址：https://raw.githubusercontent.com/Hunlongyu/ZY-Player/master/src/lib/dexie/iniData/Iptv.json
def matcher_watch_tv(text):
    matchObj = re.match(r'打开中央(.+)台', text)
    if matchObj is not None:
        num = format_number(matchObj.group(1))
        if num == 1:
            return 'http://39.134.65.162/PLTV/88888888/224/3221225686/index.m3u8'
        elif num == 2:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225747/index.m3u8'
        elif num == 3:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225785/index.m3u8'
        elif num == 4:
            return 'http://39.134.65.162/PLTV/88888888/224/3221225487/index.m3u8'
        elif num == 5:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225753/index.m3u8'
        elif num == 6:
            return 'http://39.134.65.162/PLTV/88888888/224/3221225786/index.m3u8'
        elif num == 7:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225733/index.m3u8'
        elif num == 8:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225750/index.m3u8'
        elif num == 9:
            return 'http://ottrrs.hl.chinamobile.com/PLTV/88888888/224/3221225734/index.m3u8'
        elif num == 10:
            return 'http://112.50.243.8/PLTV/88888888/224/3221225814/1.m3u8'
        elif num == 11:
            return 'http://dbiptv.sn.chinamobile.com/PLTV/88888888/224/3221225499/1.m3u8'
        elif num == 12:
            return 'http://39.134.65.162/PLTV/88888888/224/3221225518/index.m3u8'
        elif num == 13:
            return 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226316/1.m3u8'
        elif num == 14:
            return 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226229/1.m3u8'
        elif num == 15:
            return 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226333/1.m3u8'
        elif num == 17:
            return 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226318/1.m3u8'

    matchObj = re.match(r'打开(湖北|湖南|四川|吉林|海南|东南|广东|江苏|东方|云南|北京|浙江|天津|广西|山东|安徽|辽宁|重庆|陕西|北京)卫视', text)
    if matchObj is not None:
        name = matchObj.group(1)
        obj = {
            '湖北': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226240/1.m3u8',
            '湖南': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226241/1.m3u8',
            '四川': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226523/1.m3u8',
            '吉林': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225886/1.m3u8',
            '海南': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225639/1.m3u8',
            '东南': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225876/1.m3u8',
            '广东': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226535/1.m3u8',
            '江苏': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225887/1.m3u8',
            '东方': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226161/1.m3u8',
            '云南': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226543/1.m3u8',
            '北京': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226160/1.m3u8',
            '浙江': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225903/1.m3u8',
            '天津': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225899/1.m3u8',
            '广西': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226534/1.m3u8',
            '山东': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226487/1.m3u8',
            '安徽': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226490/1.m3u8',
            '辽宁': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221225889/1.m3u8',
            '重庆': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226518/1.m3u8',
            '陕西': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226532/1.m3u8',
            '北京': 'http://221.179.217.9/otttv.bj.chinamobile.com/PLTV/88888888/224/3221226224/1.m3u8'
        }
        if name in obj:
            return obj[name]

def matcher_watch_video(text):
    matchObj = re.match(r'打开电视剧(.+)第(.+)集', text)
    if matchObj is not None:
        name = matchObj.group(1)
        num = int(format_number(matchObj.group(2)))
        if name is not None and num is not None:
            return (name, num)

def matcher_watch_movie(text):
    matchObj = re.match(r'打开电影(.+)', text)
    if matchObj is not None:
        name = matchObj.group(1)
        if name is not None:
            return (name)

async def http_code(url):
    async with aiohttp.request("GET", url) as response:
        return response.status

async def http_get(url):
    async with aiohttp.request("GET", url) as response:
        return json.loads(await response.text())

# 获取本地视频链接
async def get_local_video_url(video_path, name, num):
    if video_path == '':
        return None
    _url = f'{video_path}/{name}'
    print(f'查找资源：')
    # 判断是否为链接
    if video_path[:4] == 'http':
        # 暂时还没想好怎么处理
        return None
    elif os.path.exists(_url):
        # 读取目录里的文件
        files = os.listdir(_url)
        for f in files:
            if os.path.isfile(f'{_url}/{f}'):
                # 判断集数是否存在
                arr = f.split('.')
                if arr[0] == str(num):
                    return f'{name}/{f}'

# 获取视频链接
async def get_video_url(name, num):
    print(f'{name} - {num}')
    _url = f'https://api.okzy.tv/api.php/provide/vod/at/json/?ac=detail&wd={name}'
    print(_url)
    data = await http_get(_url)
    # print(data)
    if data['total'] > 0:
        for obj in data['list']:
            # 如果没有播放地址，则去找下一个
            vod_play_url = obj.get('vod_play_url', '')
            if vod_play_url == '':
                continue
            # 获取m3u8列表
            vod_play_url_list = vod_play_url.split('$$$')
            url_list = vod_play_url_list[1]
            # 判断后缀格式
            if url_list[-5:] != '.m3u8':
                url_list = vod_play_url_list[0]
            ''' 电影 '''
            if num == -1:
                arr = url_list.split('$')
                if len(arr) > 1:
                    return arr[len(arr) - 1]
            else:
                # 匹配集数
                matchObj = re.findall(r'第(\d+)集\$(.*?)m3u8', url_list)
                # 如果集数，大于当前列表，则去找下一个
                if num > len(matchObj):
                    continue
                # 遍历当前视频集合
                for item in matchObj:
                    print(item)
                    if int(item[0]) == num:
                        return f'{item[1]}m3u8'
    return None

########################################## 接口配置
class ApiConfig():

    def __init__(self, _dir):
        if os.path.exists(_dir) == False:           
            self.mkdir(_dir)
        self.dir = _dir

    def get_config(self):
        content = self.read('conversation.json')
        if content is None:
            content = {}
        return content

    def save_config(self, data):
        content = self.get_config()
        content.update(data)
        self.write('conversation.json', content)

    # 创建文件夹
    def mkdir(self, path):
        folders = []
        while not os.path.isdir(path):
            path, suffix = os.path.split(path)
            folders.append(suffix)
        for folder in folders[::-1]:
            path = os.path.join(path, folder)
            os.mkdir(path)

    # 获取路径
    def get_path(self, name):
        return self.dir + '/' + name

    # 读取文件内容
    def read(self, name):
        fn = self.get_path(name)
        if os.path.isfile(fn):
            with open(fn,'r', encoding='utf-8') as f:
                content = json.load(f)
                return content
        return None

    # 写入文件内容
    def write(self, name, obj):
        with open(self.get_path(name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False)
