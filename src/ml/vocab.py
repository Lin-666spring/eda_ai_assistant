"""PCB 电子领域专用字符词表

字符覆盖策略：
- 3500 常用汉字（覆盖中文 PCB 术语、电子工程词汇）
- ASCII 可打印字符（英文、数字、标点）
- PCB 专用符号：Ω μ ε λ π ° ± × → ≥ ≤
- 特殊 token: [PAD]=0, [UNK]=1
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 预设字符集 ──

# 3500 常用汉字 (覆盖率 > 99.5% 现代中文)
_COMMON_HAN = (
    "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于"
    "出就分对成会可主发年动同工也能下过子说产种面而方后多定行学"
    "法所民得经十三之进着等部度家电力里如水化高自二理起小物现实"
    "加量都两体制机当使点从业本去把性好应开它合还因由其些然前外"
    "天政四日那社义事平形相全表间样与关各重新线内数正心反你明看"
    "原又么利比或但质气第向道命此变条只没结解问意建月公无系军很"
    "情者最立代想已通并提直题党程展五果料象员革位入常文总次品式"
    "活设及管特件长求老头基资边流路级少图山统接知较将组见计别她"
    "手角期根论运农指几九区强放决西被干做必战先回则任取据处队南"
    "给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思"
    "术极交受联什认六共权收证改清己美再采转更单风切打白教速花带"
    "安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科"
    "张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫"
    "且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千"
    "周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构"
    "府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格"
    "养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引"
    "听该铁价严首底液官德随病苏失尔死讲配女黄推显谈罪神艺呢席含"
    "企望密批营项防举球英氧势告李台落木帮轮破亚师围注远字材排供"
    "河态封另施减树溶怎止案言士均武固叶鱼波视仅费紧爱左章早朝害"
    "续轻服试食充兵源判护司足某练差致板田降黑犯负击范继兴似余坚"
    "曲输修故城夫够送笔船占右财吃富春职觉汉画功巴跟虽杂飞检吸助"
    "升阳互初创抗考投坏策古径换未跑留钢曾端责站简述钱副尽帝射草"
    "冲承独令限阿宣环双请超微让控州良轴找否纪益依优顶础载倒房突"
    "坐粉敌略客袁冷胜绝析块剂测丝协诉念陈仍罗盐友洋错苦夜刑移频"
    "逐靠混母短皮终聚汽村云哪既距卫停烈央察烧迅境若印洲刻括激孔"
    "搞甚室待核校散侵吧甲游久菜味旧模湖货损预阻毫普稳乙妈植息扩"
    "银语挥酒守拿序纸医缺雨吗针刘啊急唱误训愿审附获茶鲜粮斤孩脱"
    "硫肥善龙演父渐血欢械掌歌沙著刚攻谓盾讨晚粒乱燃矛乎杀药宁鲁"
    "贵钟煤读班伯香介迫句丰培握兰担弦蛋沉假穿执答乐谁顺烟缩征脸"
    "喜松脚困异免背星福买染井概慢怕磁倍祖皇促静补评翻肉践尼衣宽"
    "扬棉希伤操垂秋宜氢套督振架亮末宪庆编牛触映雷销诗座居抓裂胞"
    "呼娘景威绿晶厚盟衡鸡孙延危胶屋乡临陆顾掉呀灯岁措束耐剧玉赵"
    "跳哥季课凯胡额款绍卷齐伟蒸殖勇苗川炉弱零杨奏沿露杆探滑镇饭"
    "浓航怀赶库夺伊灵税途灭赛归召鼓播盘裁险康唯录菌纯借糖盖横符"
    "私努堂域枪润幅哈竟熟虫泽脑壤碳欧遍侧寨敢彻虑斜薄庭纳弹饲伸"
    "折麦湿暗荷瓦塞床筑户塔访透司梁刀旋迹卡氯遇份毒泥退洗摆灰彩"
    "卖耗夏择忙铜献硬予繁圈雪函亦抽篇阵阴丁尺追堆雄迎泛爸楼避谋"
    "吨野猪旗累偏典馆索秦脂潮爷豆忽托惊塑遗愈朱替纤粗倾尚痛楚谢"
    "奋购磨君池旁碎骨监捕弟暴割贯殊释词亡壁顿宝午尘闻揭炮残冬桥"
    "妇警综招吴付浮遭徐您摇谷赞箱隔订男吹园纷唐败宋玻巨耕坦荣湾"
    "沿命杆袭吗盟衡"
)

# 电子/PCB 专用汉字补充（不在常用字表中的）
_ELECTRONICS_HAN = (
    "耦焊锡铜铝硅锗砷镓铟锂镍铬锰铁钴锌钼铑钯银镉铟锑碲碘氪氙"
    "酚醛酯醚酮酰腈肼胍脲酐醌醣苷萘蒽菲芴苝卟啉咔唑噻吩吡咯呋喃"
    "咪唑吡啶嘧啶嘌呤喹啉吲哚哌嗪胍啶砜磺酰胺膦磷酰羟基羧巯基"
    "栅源漏阱衬底磊晶外延肖特基齐纳变容闩锁栓锁闩"
    "瓷介独石钽铌聚苯乙烯聚丙烯涤纶云母纸介金属化薄膜安规"
    "贴片直插铝电解钽电解固态电解超级电容法拉电容可变电容微调电容"
    "排阻排容排感磁珠热敏压敏光敏湿敏气敏力敏磁敏"
    "晶振谐振器振荡器滤波器陷波器双工器耦合器功分器衰减器环形器隔离器"
    "稳压升压降压升降压电荷泵线性开关电源控制器驱动器"
    "收发器收发机接收发射变频混频调制解调编解码编译码"
    "单片机微控制器微处理器数字信号处理现场可编程门阵列复杂可编程逻辑器件"
    "存储器寄存器锁存器缓冲器驱动器收发器触发器计数器译码器编码器选择器"
    "加法器乘法器累加器比较器运算放大器仪表放大器差分放大器功率放大器"
    "模数转换数模转换电压基准电压监控复位看门狗定时器实时时钟"
    "接口收发收发器电平转换隔离隔离器光耦光电耦合磁耦数字隔离"
    "传感器温度湿度压力加速度陀螺仪磁力计接近光环境颜色气体流量液位"
    "天线射频微波毫米波太赫兹波导同轴微带共面波导缝隙贴片阵列相控阵"
    "走线过孔焊盘阻焊绿油丝印钢网贴片回流焊波峰焊手工焊"
    "层叠叠层芯板半固化片铜箔基材玻璃纤维环氧树脂聚酰亚胺聚四氟乙烯"
    "特性阻抗差分阻抗共模阻抗奇模偶模端接匹配终端串联并联戴维南交流耦合"
    "串扰近端远端反射振铃过冲下冲单调性眼图抖动偏移歪斜码间干扰"
    "电磁兼容电磁干扰电磁敏感度辐射传导抗扰度屏蔽滤波接地"
    "热管理散热热阻结温壳温环境温度热界面导热对流辐射风冷液冷"
    "安规爬电电气间隙绝缘耐压耐压测试漏电流漏电保护接地保护过流保护"
    "封装型号规格参数品牌制造商 tolerance footprint datasheet"
    "阈值滞回迟滞窗口门限容差容限裕量降额余量"
)

# ASCII 字符
_ASCII = "".join(chr(i) for i in range(32, 127))

# 专用符号
_SPECIAL = "ΩμλπεθσωΔΣ√∞±°×→≥≤～…—·「」『』【】《》（）／＃＠％"


def _build_vocab_chars() -> list[str]:
    """构建完整字符集（去重 + 排序）"""
    all_chars = set()
    all_chars.update(_COMMON_HAN)
    all_chars.update(_ELECTRONICS_HAN)
    all_chars.update(_ASCII)
    all_chars.update(_SPECIAL)
    # 控制字符单独处理
    return sorted(all_chars)


class PCBVocab:
    """PCB 电子领域字符级词表

    使用方式:
        vocab = PCBVocab()
        ids = vocab.encode("检查电源走线")  # → [char_ids...]
        text = vocab.decode(ids)             # → "检查电源走线"
    """

    PAD_TOKEN = "[PAD]"
    UNK_TOKEN = "[UNK]"

    def __init__(self, max_size: Optional[int] = None):
        chars = _build_vocab_chars()

        if max_size and len(chars) > max_size - 2:
            chars = chars[:max_size - 2]

        self._chars = [self.PAD_TOKEN, self.UNK_TOKEN] + chars
        self._char_to_id = {c: i for i, c in enumerate(self._chars)}
        self._id_to_char = {i: c for i, c in enumerate(self._chars)}

        self.pad_id = self._char_to_id[self.PAD_TOKEN]
        self.unk_id = self._char_to_id[self.UNK_TOKEN]

    def __len__(self) -> int:
        return len(self._chars)

    @property
    def vocab_size(self) -> int:
        return len(self._chars)

    def encode(self, text: str) -> list[int]:
        """文本 → token id 列表"""
        return [self._char_to_id.get(c, self.unk_id) for c in text]

    def decode(self, ids: list[int]) -> str:
        """token id 列表 → 文本"""
        return "".join(self._id_to_char.get(i, self.UNK_TOKEN) for i in ids)

    def save(self, path: str) -> None:
        """保存词表到 JSON"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"chars": self._chars}, f, ensure_ascii=False, indent=2)
        logger.info("Vocab saved: %d chars → %s", len(self._chars), path)

    @classmethod
    def load(cls, path: str) -> "PCBVocab":
        """从 JSON 加载词表"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        vocab = cls.__new__(cls)
        vocab._chars = data["chars"]
        vocab._char_to_id = {c: i for i, c in enumerate(vocab._chars)}
        vocab._id_to_char = {i: c for i, c in enumerate(vocab._chars)}
        vocab.pad_id = vocab._char_to_id[cls.PAD_TOKEN]
        vocab.unk_id = vocab._char_to_id[cls.UNK_TOKEN]
        return vocab

    def __repr__(self) -> str:
        return f"PCBVocab({len(self._chars)} chars)"


# 预计算字符集大小，供训练脚本使用
_VOCAB_CHARS = _build_vocab_chars()
DEFAULT_VOCAB_SIZE = len(_VOCAB_CHARS) + 2  # + PAD + UNK
