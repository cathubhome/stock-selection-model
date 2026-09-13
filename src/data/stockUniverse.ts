import { StockBasic, ScoredStock } from '../types';

export const INITIAL_STOCK_POOL: StockBasic[] = [
  { symbol: '000026', name: '飞亚达', pinyin: 'FYD', industry: '消费电子/精密制造', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000034', name: '神州数码', pinyin: 'SZSM', industry: 'IT服务/云计算', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000676', name: '智度股份', pinyin: 'ZDGF', industry: '互联网/数字营销', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000729', name: '燕京啤酒', pinyin: 'YJPJ', industry: '食品饮料/啤酒', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000759', name: '中百集团', pinyin: 'ZBJT', industry: '商业零售', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000892', name: '欢瑞世纪', pinyin: 'HRSJ', industry: '影视传媒', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '000938', name: '紫光股份', pinyin: 'ZGGF', industry: '通信设备/算力网络', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '001330', name: '博纳影业', pinyin: 'BNYY', industry: '影视传媒', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002080', name: '中材科技', pinyin: 'ZCKJ', industry: '新材料/风电叶片', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002083', name: '孚日股份', pinyin: 'FRGF', industry: '纺织制造/锂电材料', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002156', name: '通富微电', pinyin: 'TFMD', industry: '半导体封测', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002281', name: '光迅科技', pinyin: 'GXKJ', industry: '光通信/光模块', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002353', name: '杰瑞股份', pinyin: 'JRGF', industry: '专用设备/油气装备', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002384', name: '东山精密', pinyin: 'DSJM', industry: '电子元件/PCB', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002407', name: '多氟多', pinyin: 'DFD', industry: '化工/氟化工/电池电解液', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002512', name: 'ST达华', pinyin: 'STDH', industry: '通信终端', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002517', name: '恺英网络', pinyin: 'KYWL', industry: '网络游戏', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002552', name: '宝鼎科技', pinyin: 'BDKJ', industry: '通用机械/大型铸锻件', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002579', name: '中京电子', pinyin: 'ZJDZ', industry: '印制电路板', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002739', name: '儒意电影', pinyin: 'RYDY', industry: '影视传媒', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002747', name: '埃斯顿', pinyin: 'ASD', industry: '工业机器人/自动化', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002832', name: '比音勒芬', pinyin: 'BYLF', industry: '服装服饰/中高端服饰', market: '主板', source: '检索多选导入', added_at: '2026-08-11' },
  { symbol: '002851', name: '麦格米特', pinyin: 'MGMT', industry: '电气设备/电源系统', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002957', name: '科瑞技术', pinyin: 'KRJS', industry: '工业自动化/锂电设备', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '002975', name: '博杰股份', pinyin: 'BJGF', industry: '仪器仪表/工业测试', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '003001', name: '中岩大地', pinyin: 'ZYDD', industry: '建筑装饰/岩土工程', market: '主板', source: '检索多选导入', added_at: '2026-08-11' },
  { symbol: '300189', name: '神农种业', pinyin: 'SNZY', industry: '农林牧渔/育种', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300191', name: '潜能恒信', pinyin: 'QNHX', industry: '油气勘探/地震数据解释', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300209', name: '行云科技', pinyin: 'XYKJ', industry: '跨境电商/供应链', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300285', name: '国瓷材料', pinyin: 'GCCL', industry: '特种无机非金属材料', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300476', name: '胜宏科技', pinyin: 'SHKJ', industry: '高多层PCB/算力加速卡板', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300622', name: '博士眼镜', pinyin: 'BSYJ', industry: '商业贸易/智能眼镜渠道', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300666', name: '江丰电子', pinyin: 'JFDZ', industry: '超高纯靶材/半导体材料', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300726', name: '宏达电子', pinyin: 'HDDZ', industry: '特种陶瓷电容器', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300776', name: '帝尔激光', pinyin: 'DEJG', industry: '光伏激光加工设备', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300863', name: '卡倍亿', pinyin: 'KBY', industry: '汽车线缆/高压新能源线缆', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '300996', name: '普联软件', pinyin: 'PLRJ', industry: '大型集团财务与业务软件', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '301133', name: '柏诚股份', pinyin: 'BCGF', industry: '工业洁净室工程', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '301191', name: '菲菱科思', pinyin: 'FLKS', industry: '数据通信/交换机ODM', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '301217', name: '铜冠铜箔', pinyin: 'TGTB', industry: '电子铜箔/锂电箔', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '301291', name: '明阳电气', pinyin: 'MYDQ', industry: '变压器/新能源升压站', market: '创业板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '513050', name: '中概互联ETF', pinyin: 'ZGHL', industry: '海外科技巨头ETF', market: 'ETF', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '561380', name: '电网设备ETF', pinyin: 'DWSB', industry: '特高压/智能电网', market: 'ETF', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '561760', name: '油气ETF', pinyin: 'YQETF', industry: '上游资源/原油天然气', market: 'ETF', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '562590', name: '半导体设备ETF', pinyin: 'BDTSB', industry: '芯片前道制造设备', market: 'ETF', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600110', name: '诺德股份', pinyin: 'NDGF', industry: '锂电铜箔', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600166', name: '福田汽车', pinyin: 'FTQC', industry: '商用车/轻卡重卡', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600172', name: '黄河旋风', pinyin: 'HHXF', industry: '超硬材料/人造金刚石', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600176', name: '中国巨石', pinyin: 'ZGJS', industry: '玻璃纤维新材料', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600188', name: '兖矿能源', pinyin: 'YKNY', industry: '煤炭开采/煤化工', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '600498', name: '烽火通信', pinyin: 'FHTX', industry: '光传输/光缆网络', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '601058', name: '赛轮轮胎', pinyin: 'SLLT', industry: '轮胎制造/液体黄金技术', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '601118', name: '海南橡胶', pinyin: 'HNXJ', industry: '天然橡胶种植与深加工', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '601208', name: '东材科技', pinyin: 'DCKJ', industry: '光学膜材料/特种树脂', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603011', name: '合锻智能', pinyin: 'HDZN', industry: '成形机床/光电色选机', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603026', name: '石大胜华', pinyin: 'SDSH', industry: '碳酸酯溶剂/锂电添加剂', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603318', name: '水发燃气', pinyin: 'SFRQ', industry: '燃气输配与LNG装备', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603466', name: '风语筑', pinyin: 'FYZ', industry: '数字化展馆/文旅互动', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603533', name: '掌阅科技', pinyin: 'ZYKJ', industry: '数字阅读/短剧IP', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603650', name: '彤程新材', pinyin: 'TCXC', industry: '半导体光刻胶/特种树脂', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603893', name: '瑞芯微', pinyin: 'RXW', industry: '端侧AI芯片/SoC芯片', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603929', name: '亚翔集成', pinyin: 'YXJC', industry: '洁净室高科技工程', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '603936', name: '博敏电子', pinyin: 'BMDZ', industry: '高频高速PCB/IC载板', market: '主板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688008', name: '澜起科技', pinyin: 'LQKJ', industry: '内存接口芯片/津逮CPU', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688017', name: '绿的谐波', pinyin: 'LDXB', industry: '谐波减速器/人形机器人关节', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688019', name: '安集科技', pinyin: 'AJKJ', industry: '化学机械抛光液CMP', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688031', name: '星环科技', pinyin: 'XHKJ', industry: '大数据基础软件/向量库', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688146', name: '中船特气', pinyin: 'ZCTQ', industry: '电子特种气体/高纯三氟化氮', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688158', name: '优刻得', pinyin: 'UKD', industry: '中立第三方云计算/智算中心', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688207', name: '格灵深瞳', pinyin: 'GLST', industry: '计算机视觉/三维大模型', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688257', name: '新锐股份', pinyin: 'XRGF', industry: '硬质合金/凿岩工具', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688531', name: '日联科技', pinyin: 'RLKJ', industry: '工业X射线检测/微焦点射线源', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688598', name: '金博股份', pinyin: 'JBGF', industry: '碳基复合材料/光伏热场', market: '科创板', source: '检索多选导入', added_at: '2026-08-14' },
  { symbol: '688667', name: '菱电电控', pinyin: 'LDDK', industry: '汽车电子/发动机ECU', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: '688702', name: '盛科通信', pinyin: 'SKTX', industry: '以太网交换芯片', market: '科创板', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: 'HK1024', name: '快手-W', pinyin: 'KS', industry: '短视频/直播电商', market: '港股通', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: 'HK1093', name: '石药集团', pinyin: 'SYJT', industry: '创新药/mRNA疫苗', market: '港股通', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: 'HK2476', name: '胜宏科技(港)', pinyin: 'SHKJHK', industry: '高端印制电路板', market: '港股通', source: '历史对话提取', added_at: '2026-08-10' },
  { symbol: 'HK9992', name: '泡泡玛特', pinyin: 'PPMT', industry: '潮流玩具/IP运营', market: '港股通', source: '历史对话提取', added_at: '2026-08-10' },
];

export const FULL_UNIVERSE_SEARCHABLE: StockBasic[] = [
  ...INITIAL_STOCK_POOL,
  { symbol: '600519', name: '贵州茅台', pinyin: 'GZMT', industry: '白酒', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '300750', name: '宁德时代', pinyin: 'NDSD', industry: '动力电池', market: '创业板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '002594', name: '比亚迪', pinyin: 'BYD', industry: '新能源汽车', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '601318', name: '中国平安', pinyin: 'ZGPA', industry: '金融/保险', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '600036', name: '招商银行', pinyin: 'ZSYH', industry: '金融/银行', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '000333', name: '美的集团', pinyin: 'MDJT', industry: '白色家电', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '601899', name: '紫金矿业', pinyin: 'ZJKY', industry: '有色金属/金铜', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '600900', name: '长江电力', pinyin: 'CJDL', industry: '电力/公用事业', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '002475', name: '立讯精密', pinyin: 'LXJM', industry: '消费电子/代工制造', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '601138', name: '工业富联', pinyin: 'GYFL', industry: 'AI服务器/云计算', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '688981', name: '中芯国际', pinyin: 'ZXGJ', industry: '晶圆代工制造', market: '科创板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '300308', name: '中际旭创', pinyin: 'ZJXC', industry: '光模块/800G光通信', market: '创业板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '300502', name: '新易盛', pinyin: 'XYS', industry: '光模块/光器件', market: '创业板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '688041', name: '海光信息', pinyin: 'HGXX', industry: '国产CPU/DCU芯片', market: '科创板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '688256', name: '寒武纪', pinyin: 'HWJ', industry: 'AI算力芯片', market: '科创板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '000001', name: '平安银行', pinyin: 'PAYH', industry: '银行', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '600000', name: '浦发银行', pinyin: 'PFYH', industry: '银行', market: '主板', source: '全市场大盘', added_at: '2026-08-15' },
  { symbol: '510300', name: '沪深300ETF', pinyin: 'HS300', industry: '宽基指数ETF', market: 'ETF', source: '基准指数', added_at: '2026-08-15' },
  { symbol: '159919', name: '嘉实沪深300ETF', pinyin: 'JSHS300', industry: '宽基指数ETF', market: 'ETF', source: '基准指数', added_at: '2026-08-15' },
  { symbol: '588000', name: '科创50ETF', pinyin: 'KC50', industry: '硬科技宽基ETF', market: 'ETF', source: '基准指数', added_at: '2026-08-15' }
];

// Helper to deterministically generate consistent, realistic quant metrics for each stock
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function generateScoredStocks(stocks: StockBasic[]): ScoredStock[] {
  return stocks.map((s, index) => {
    const h = hashString(s.symbol + s.name);
    const basePrice = 12 + (h % 14500) / 100;
    const priceChange = ((h % 1600) - 750) / 100; // -7.5% to +8.5%
    const turnover = 1.2 + ((h * 7) % 980) / 100; // 1.2% - 11.0%
    const volumeRatio = 0.65 + ((h * 13) % 240) / 100; // 0.65 - 3.05
    const pe = 12 + ((h * 3) % 650) / 10;
    const pb = 1.1 + ((h * 5) % 85) / 10;

    // Feature values
    const ret_20 = ((h % 500) - 180) / 10; // -18% to +32%
    const ret_60 = (((h * 3) % 700) - 250) / 10; // -25% to +45%
    const vol_20 = 0.18 + ((h * 11) % 450) / 1000; // 18% to 63%

    // Component scores (0-100)
    const model_score = Math.min(99, Math.max(12, 45 + ((h * 17) % 52) + (ret_20 > 10 ? 8 : -4)));
    const technical_score = Math.min(99, Math.max(10, 40 + ((h * 19) % 55) + (ret_20 > 5 ? 6 : -5)));
    const volume_price_score = Math.min(99, Math.max(15, 38 + ((h * 23) % 58) + (volumeRatio > 1.5 ? 9 : -3)));
    const candle_score = Math.min(99, Math.max(20, 35 + ((h * 29) % 60)));

    // Sentiment score
    const hasNews = (h % 5) !== 0;
    const news_count = hasNews ? 2 + ((h * 7) % 18) : 0;
    const sentiment_score = hasNews ? Math.min(95, Math.max(25, 48 + ((h * 31) % 46))) : 50.0;
    const sentiment_source = hasNews 
      ? (h % 3 === 0 ? '财联社/研报关键词分析' : (h % 3 === 1 ? '同花顺/互动易监测' : '东方财富公开资讯'))
      : '未提供/默认中性';

    // Diagnostic status
    const trading_days = 240 + ((h * 3) % 15);
    let diagnostic_status: 'excellent' | 'good' | 'warning' = 'excellent';
    let diagnostic_message = '数据完整无缺失，量价序列健全';
    if (s.symbol.startsWith('ST')) {
      diagnostic_status = 'warning';
      diagnostic_message = '风险警示标的，日线波动率异常，建议降低仓位限制';
    } else if (trading_days < 245) {
      diagnostic_status = 'good';
      diagnostic_message = '近期存在少量节假日或停牌休市，已前值填充';
    }

    // Odds calculations
    const rewardRisk = Number((1.2 + ((h * 41) % 250) / 100).toFixed(2));
    const winRate = Number((48 + ((h * 43) % 360) / 10).toFixed(1));
    const expectedReturn = Number((4.5 + ((h * 47) % 220) / 10).toFixed(1));

    // Default weights: 35% model, 25% technical, 20% volume_price, 10% candle, 10% sentiment
    const composite_score = Number((
      model_score * 0.35 +
      technical_score * 0.25 +
      volume_price_score * 0.20 +
      candle_score * 0.10 +
      sentiment_score * 0.10
    ).toFixed(1));

    return {
      symbol: s.symbol,
      name: s.name,
      pinyin: s.pinyin,
      industry: s.industry,
      market: s.market,
      source: s.source || '本地股票池',
      added_at: s.added_at || '2026-08-10',
      price: Number(basePrice.toFixed(2)),
      change: Number(priceChange.toFixed(2)),
      turnover: Number(turnover.toFixed(2)),
      volume_ratio: Number(volumeRatio.toFixed(2)),
      volume: 15000 + (h % 85000) * 100,
      amount: Math.round(basePrice * (15000 + (h % 85000) * 100) * 100),
      pe_ttm: Number(pe.toFixed(1)),
      pb: Number(pb.toFixed(2)),
      high_52w: Number((basePrice * 1.35).toFixed(2)),
      low_52w: Number((basePrice * 0.72).toFixed(2)),
      model_raw: Number(((h % 1000) / 1000 - 0.4).toFixed(4)),
      model_score,
      technical_score,
      volume_price_score,
      candle_score,
      sentiment_score,
      sentiment_source,
      news_count,
      composite_score,
      rank: index + 1,
      odds_reward_risk: rewardRisk,
      odds_win_rate: winRate,
      odds_expected_return: expectedReturn,
      diagnostic_status,
      diagnostic_message,
      trading_days,
    };
  });
}
