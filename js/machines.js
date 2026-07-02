/** 各展區機台指標與介紹（展區 id 對應 zones.js） */
const PRODUCT_MENU = [
  { label: '產品圖示', action: 'images' },
  { label: '產品型錄', action: 'catalog' },
  { label: '應用案例', action: 'cases' },
  { label: '聯絡我們', action: 'contact', href: 'https://www.litz.com.tw/' },
];

const COLD_INTRO = '冷式壓鑄機適合中小型至大型精密鑄件，兼具節能與穩定射出性能。';
const COLD2_INTRO = '第二展區展示冷式壓鑄產線配置，鎖模力與循環效率均衡，適合量產應用。';

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
      name: 'ZDC-420 TCSA',
      subtitle: '冷式壓鑄機 · 第一展區左側機台',
      position: { yaw: '-100deg', pitch: '-32deg' },
      focus: { yaw: '-100deg', pitch: '3deg', zoom: 50 },
      intro: COLD_INTRO,
      photos: [photo('ZDC-420TCSA')],
      presenterVideo: presenterVideo('ZDC-420TCSA'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z1-center',
      name: 'ZDC-250TCSA',
      subtitle: '冷式壓鑄機 · 第一展區中央機台',
      position: { yaw: '3deg', pitch: '-32deg' },
      focus: { yaw: '3deg', pitch: '3deg', zoom: 51 },
      intro: COLD_INTRO,
      photos: [photo('ZDC-250TCSA')],
      presenterVideo: presenterVideo('ZDC-250TCSA'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z1-right',
      name: 'ZDC-180 TCSA',
      subtitle: '冷式壓鑄機 · 第一展區右側機台',
      position: { yaw: '73deg', pitch: '-32deg' },
      focus: { yaw: '73deg', pitch: '3deg', zoom: 50 },
      intro: COLD_INTRO,
      photos: [photo('ZDC-180TCSA')],
      presenterVideo: presenterVideo('ZDC-180TCSA'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-2': [
    {
      id: 'z2-left',
      name: 'ZDC-560TCSA',
      subtitle: '冷式壓鑄機 · 第二展區左側機台',
      position: { yaw: '-100deg', pitch: '-32deg' },
      focus: { yaw: '-100deg', pitch: '3deg', zoom: 50 },
      intro: COLD2_INTRO,
      photos: [photo('ZDC-560TCSA')],
      presenterVideo: presenterVideo('ZDC-560TCSA'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z2-center',
      name: 'ZDC-1100TCM',
      subtitle: '冷式壓鑄機 · 第二展區中央機台',
      position: { yaw: '0deg', pitch: '-32deg' },
      focus: { yaw: '0deg', pitch: '3deg', zoom: 51 },
      intro: COLD2_INTRO,
      photos: [photo('ZDC-1100TCM')],
      presenterVideo: presenterVideo('ZDC-1100TCM'),
      menu: PRODUCT_MENU,
    },
    {
      id: 'z2-right',
      name: 'ZDC-900TCSA',
      subtitle: '冷式壓鑄機 · 第二展區右側機台',
      position: { yaw: '73deg', pitch: '-32deg' },
      focus: { yaw: '73deg', pitch: '3deg', zoom: 50 },
      intro: COLD2_INTRO,
      photos: [photo('ZDC-900TCSA')],
      presenterVideo: presenterVideo('ZDC-900TCSA'),
      menu: PRODUCT_MENU,
    },
  ],
  'zone-3': [
    {
      id: 'hot-press-1',
      name: 'ZHC-130TCS',
      subtitle: '熱式壓鑄機 · 熱室',
      /* 機台位於畫面中央；指標置於機台正前方地面，點選拉近正對機台（約佔 8 成） */
      position: { yaw: '-2deg', pitch: '-32deg' },
      focus: { yaw: '-2deg', pitch: '3deg', zoom: 51 },
      intro: '熱式壓鑄機適合鋅、鎂等低熔點合金，射出速度快、適合薄壁複雜件。',
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
      /* 機台位於左側（中心約 -100°）；指標置於機台正前方地面，點選拉近正對機台（約佔 8 成） */
      position: { yaw: '-100deg', pitch: '-32deg' },
      focus: { yaw: '-100deg', pitch: '4deg', zoom: 50 },
      intro: '重力鑄造適合大型鋁件與結構件，設備穩定、維護簡便，廣泛用於汽機車與工業零件。',
      photos: [photo('PMC-1000A')],
      presenterVideo: presenterVideo('PMC-1000A'),
      menu: PRODUCT_MENU,
    },
  ],
};

export function getMachinesForScene(sceneId) {
  return SCENE_MACHINES[sceneId] ?? [];
}
