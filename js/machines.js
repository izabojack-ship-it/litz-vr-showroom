/** 各展區機台指標與介紹（展區 id 對應 zones.js） */
const PRODUCT_MENU = [
  { label: '產品圖示', action: 'images' },
  { label: '產品型錄', action: 'catalog' },
  { label: '應用案例', action: 'cases' },
  { label: '聯絡我們', action: 'contact', href: 'https://www.zitai.com/zh-tw/contact.html' },
];

/* 機台照片放於 media/machines/；photos 為 { full, thumb } 陣列（可多張）
 * 真人介紹影片放於 media/presenter/，檔名與機台型號一致，例如 ZDC-1100TCM.mp4
 */
const photo = (base) => ({ full: `${base}.jpg`, thumb: `${base}_thumb.jpg` });
const presenterVideo = (base) => `${base}.mp4`;

/*
 * 指標(position)置於機台正前方地面(pitch -32)；
 * 點選後 focus 拉近正對機台，機台幾乎填滿畫面、具臨場感。
 * name = 機台型號；photos = 機台照片。
 */
export const SCENE_MACHINES = {
  'zone-1': [
    {
      id: 'z1-left',
      name: 'ZDC-250TCSA',
      subtitle: '冷室壓鑄機 · 第一展區左側機台',
      position: { yaw: '-112deg', pitch: '-32deg' },
      focus: { yaw: '-112deg', pitch: '3deg', zoom: 50 },
      intro: "ZDC-250T 冷室壓鑄機，主要應用於中小型鋁合金鑄件與多元產業零件生產。此機型在設備結構、射出控制與操作便利性之間取得良好平衡，適合一般工業零件、電子零件、五金零件及汽機車相關零件製造。透過穩定的射出系統與控制介面，可協助操作人員掌握生產條件，提升成品一致性。ZDC-250T 是兼具實用性與生產效率的冷室壓鑄設備選擇。",
      photos: [photo('ZDC-250TCSA')],
      presenterVideo: presenterVideo('ZDC-250TCSA'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z1-center',
      name: 'ZDC-180 TCSA',
      subtitle: '冷室壓鑄機 · 第一展區中央機台',
      position: { yaw: '-40deg', pitch: '-32deg' },
      focus: { yaw: '-40deg', pitch: '3deg', zoom: 51 },
      intro: "ZDC-180T 冷室壓鑄機，適合中小型鋁合金鑄件生產應用。此機型具備穩定的鎖模結構與射出控制，可對應一般五金零件、工業零件與中小型精密鑄件需求。透過鋁台精機的控制系統，操作人員可依照產品條件設定射出速度、壓力與成型參數，協助提升生產穩定性與鑄件品質。ZDC-180T 適合需要穩定量產、操作簡便與製程效率的客戶使用。",
      photos: [photo('ZDC-180TCSA')],
      presenterVideo: presenterVideo('ZDC-180TCSA'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z1-right',
      name: 'ZDC-420 TCSA',
      subtitle: '冷室壓鑄機 · 第一展區右側機台',
      position: { yaw: '145deg', pitch: '-32deg' },
      focus: { yaw: '145deg', pitch: '3deg', zoom: 50 },
      intro: "ZDC-420T 冷室壓鑄機，適合中型鋁合金鑄件生產需求，廣泛應用於汽車零件、工業零件與精密鑄件製造。此機型具備穩定的機械結構與射出控制能力，可因應不同產品的成型條件。透過人機介面，操作人員可設定射出速度、壓力、行程與增壓條件，協助提升製程穩定性與產品品質。ZDC-420T 是兼顧產能、穩定性與操作效率的代表機型。",
      photos: [photo('ZDC-420TCSA')],
      presenterVideo: presenterVideo('ZDC-420TCSA'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-2': [
    {
      id: 'z2-left',
      name: 'ZDC-730TCS',
      subtitle: '冷室壓鑄機 · 第二展區左側機台',
      position: { yaw: '-115deg', pitch: '-32deg' },
      focus: { yaw: '-115deg', pitch: '3deg', zoom: 50 },
      intro: "ZDC-730T 冷室壓鑄機，適合中大型鋁合金鑄件與高產能製程需求。此機型可對應較大尺寸的鑄件生產，並具備穩定的鎖模能力與射出性能。透過控制系統的參數設定與製程監控，可協助客戶掌握射出速度、增壓壓力與成型條件，降低生產不穩定因素。ZDC-730T 適合汽車零件、機械零件及多元工業應用，協助客戶提升量產效率與鑄件品質。",
      photos: [photo('ZDC-730TCS')],
      presenterVideo: presenterVideo('ZDC-730TCS'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z2-right',
      name: 'ZDC-560TCSA',
      subtitle: '冷室壓鑄機 · 第二展區右側機台',
      position: { yaw: '150deg', pitch: '-32deg' },
      focus: { yaw: '150deg', pitch: '3deg', zoom: 51 },
      intro: "ZDC-560T 冷室壓鑄機，適用於中大型鋁合金鑄件與穩定量產需求。此機型具備優化的鎖模結構與精準的射出控制系統，可對應汽車零件、工業零件及各類中大型鑄件製造。透過鋁台精機控制系統，操作人員可靈活設定射出速度、壓力與增壓條件，有效提升製程穩定性與產品一致性。ZDC-560T 在產能與品質之間取得良好平衡，適合追求穩定生產與效率提升的客戶。",
      photos: [photo('ZDC-560TCSA')],
      presenterVideo: presenterVideo('ZDC-560TCSA'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-5': [
    {
      id: 'z5-left',
      name: 'ZDC-1100TCM',
      subtitle: '冷室壓鑄機 · 第三展區左側機台',
      position: { yaw: '-80deg', pitch: '-32deg' },
      focus: { yaw: '-80deg', pitch: '3deg', zoom: 50 },
      intro: "ZDC-1100TCM 冷室壓鑄機，為鋁台精機中大型冷室壓鑄設備，適合大型鋁合金鑄件與高穩定性製程需求。此機型具備堅固的機械結構、穩定的鎖模系統與精準的射出控制，可應用於汽車零組件、工業零件與大型鑄件生產。透過控制系統，可設定射出速度、增壓壓力與成型參數，協助客戶提升生產穩定性、鑄件品質與長期設備效能。",
      photos: [photo('ZDC-1100TCM')],
      presenterVideo: presenterVideo('ZDC-1100TCM'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z5-right',
      name: 'ZDC-900TCSA',
      subtitle: '冷室壓鑄機 · 第三展區中央機台',
      position: { yaw: '0deg', pitch: '-32deg' },
      focus: { yaw: '0deg', pitch: '3deg', zoom: 51 },
      intro: "ZDC-900T 冷室壓鑄機，主要對應中大型鋁合金鑄件生產，適合需要較高鎖模力與穩定射出控制的製程應用。此機型可應用於汽車零件、電機零件、工業結構件與多元鑄造產品。設備設計注重長時間運轉穩定性與操作便利性，搭配鋁台精機控制系統，可協助客戶進行成型條件設定、製程管理與品質控制，提升整體生產效率。",
      photos: [photo('ZDC-900TCSA')],
      presenterVideo: presenterVideo('ZDC-900TCSA'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-3': [
    {
      id: 'hot-press-1',
      name: 'ZHC-130TCS',
      subtitle: '熱室壓鑄機',
      position: { yaw: '-122deg', pitch: '-32deg' },
      focus: { yaw: '-122deg', pitch: '3deg', zoom: 51 },
      intro: "ZHC 熱室壓鑄機系列，適合鋅合金小型精密零件的快速量產。此系列機型可對應不同尺寸與不同產能需求，廣泛應用於五金零件、電子零件、扣件、飾品與精密工業零件。熱室壓鑄製程具有循環時間短、效率高與量產穩定的特點。鋁台精機透過穩定的射出機構與控制系統，協助客戶提升生產效率、成品一致性與長期製程穩定性。",
      photos: [photo('ZHC-130TCS')],
      presenterVideo: presenterVideo('ZHC-130TCS'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-4': [
    {
      id: 'gravity-cast-1',
      name: 'PMC-1000A',
      subtitle: '重力鑄造機',
      position: { yaw: '145deg', pitch: '-32deg' },
      focus: { yaw: '145deg', pitch: '4deg', zoom: 50 },
      intro: "PMC 重力鑄造機系列，適用於鋁合金重力鑄造製程，可對應不同尺寸鑄件與多元生產需求。此系列機型支援零度至九十度傾斜應用，適合需要穩定澆注、良好成型品質與彈性作業方式的客戶使用。鋁台精機重力鑄造機具備穩定的機械結構與操作控制，可應用於汽車零件、工業零件與鋁合金鑄件生產，協助提升鑄造品質與作業效率。",
      photos: [photo('PMC-1000A')],
      presenterVideo: presenterVideo('PMC-1000A'),
      menu: PRODUCT_MENU,
    },
  ],
};

export function getMachinesForScene(sceneId) {
  return SCENE_MACHINES[sceneId] ?? [];
}

