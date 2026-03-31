/* ── 页面切换 ── */
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    item.classList.add('active');
    document.getElementById('page-' + page).classList.add('active');
  });
});

/* ── Python 桥接 ── */
function pyCall(method, args) {
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.bridge) {
    window.webkit.messageHandlers.bridge.postMessage(JSON.stringify({ method, args }));
  }
}

/* ── 品牌 SVG 图标（真实 logo） ── */
const LOGO_SUIKOUSHUOA = `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="11" fill="url(#sksGrad)"/><defs><linearGradient id="sksGrad" x1="0" y1="0" x2="24" y2="24"><stop offset="0%" stop-color="#0071e3"/><stop offset="100%" stop-color="#af52de"/></linearGradient></defs><path d="M8 9.5C8 8.67 8.67 8 9.5 8h5c.83 0 1.5.67 1.5 1.5v0c0 .83-.67 1.5-1.5 1.5h-5C8.67 11 8 10.33 8 9.5z" fill="#fff" opacity=".9"/><path d="M9 13.5c0-.83.67-1.5 1.5-1.5h3c.83 0 1.5.67 1.5 1.5v0c0 .83-.67 1.5-1.5 1.5h-3c-.83 0-1.5-.67-1.5-1.5z" fill="#fff" opacity=".7"/><circle cx="7" cy="12" r="1" fill="#fff" opacity=".5"/><circle cx="17" cy="12" r="1" fill="#fff" opacity=".5"/><path d="M12 16.5v1.5M10 18h4" stroke="#fff" stroke-width="1.2" stroke-linecap="round" opacity=".6"/></svg>`;

const LOGO = {
  suikoushuoa: LOGO_SUIKOUSHUOA,
  volcengine: `<svg viewBox="0 0 24 24"><path d="M19.44 10.153l-2.936 11.586a.215.215 0 00.214.261h5.87a.215.215 0 00.214-.261l-2.95-11.586a.214.214 0 00-.412 0zM3.28 12.778l-2.275 8.96A.214.214 0 001.22 22h4.532a.212.212 0 00.214-.165.214.214 0 000-.097l-2.276-8.96a.214.214 0 00-.41 0z" fill="#00E5E5"/><path d="M7.29 5.359L3.148 21.738a.215.215 0 00.203.261h8.29a.214.214 0 00.215-.261L7.7 5.358a.214.214 0 00-.41 0z" fill="#006EFF"/><path d="M14.44.15a.214.214 0 00-.41 0L8.366 21.739a.214.214 0 00.214.261H19.9a.216.216 0 00.171-.078.214.214 0 00.044-.183L14.439.15z" fill="#006EFF"/><path d="M10.278 7.741L6.685 21.736a.214.214 0 00.214.264h7.17a.215.215 0 00.214-.264L10.688 7.741a.214.214 0 00-.41 0z" fill="#00E5E5"/></svg>`,
  aliyun: `<svg viewBox="0 0 24 24"><path d="M3.996 4.517h5.291L8.01 6.324 4.153 7.506a1.668 1.668 0 00-1.165 1.601v5.786a1.668 1.668 0 001.165 1.6l3.857 1.183 1.277 1.807H3.996A3.996 3.996 0 010 15.487V8.513a3.996 3.996 0 013.996-3.996m16.008 0h-5.291l1.277 1.807 3.857 1.182c.715.227 1.17.889 1.165 1.601v5.786a1.668 1.668 0 01-1.165 1.6l-3.857 1.183-1.277 1.807h5.291A3.996 3.996 0 0024 15.487V8.513a3.996 3.996 0 00-3.996-3.996m-4.007 8.345H8.002v-1.804h7.995z" fill="#FF6A00"/></svg>`,
  sensevoice: `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="#7c3aed"/><path d="M7 12h1.5l1.5-3 1.5 5 1.5-4 1.5 3 1.5-2H18" stroke="#fff" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  custom: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 15a3 3 0 100-6 3 3 0 000 6z" stroke="#6b7280" stroke-width="1.5"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" stroke="#6b7280" stroke-width="1.2"/></svg>`,
  openai: `<svg viewBox="0 0 24 24"><path d="M22.2819 9.8211a5.9847 5.9847 0 00-.5157-4.9108 6.0462 6.0462 0 00-6.5098-2.9A6.0651 6.0651 0 004.9807 4.1818a5.9847 5.9847 0 00-3.9977 2.9 6.0462 6.0462 0 00.7427 7.0966 5.98 5.98 0 00.511 4.9107 6.051 6.051 0 006.5146 2.9001A5.9847 5.9847 0 0013.2599 24a6.0557 6.0557 0 005.7718-4.2058 5.9894 5.9894 0 003.9977-2.9001 6.0557 6.0557 0 00-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 01-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 00.3927-.6813v-6.7369l2.02 1.1686a.071.071 0 01.038.052v5.5826a4.504 4.504 0 01-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 01-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 00.7806 0l5.8428-3.3685v2.3324a.0804.0804 0 01-.0332.0615L9.74 19.9502a4.4992 4.4992 0 01-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 012.3655-1.9728V11.6a.7664.7664 0 00.3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 01-.071 0l-4.8303-2.7865A4.504 4.504 0 012.3408 7.872zm16.5963 3.8558L13.1038 8.364l2.0153-1.1639a.0757.0757 0 01.071 0l4.8303 2.7913a4.4944 4.4944 0 01-.6765 8.1042v-5.6772a.79.79 0 00-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 00-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 01.0284-.0615l4.8303-2.7866a4.4992 4.4992 0 016.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 01-.038-.0567V6.0742a4.4992 4.4992 0 017.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 00-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997z" fill="#10a37f"/></svg>`,
  claude: `<svg viewBox="0 0 24 24"><path d="M17.3041 3.541h-3.6718l6.696 16.918H24zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456z" fill="#D4A27F"/></svg>`,
  deepseek: `<svg viewBox="0 0 24 24"><path d="M23.748 4.482c-.254-.124-.364.113-.512.234-.051.039-.094.09-.137.136-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.156-.708-.311-.955-.65-.172-.241-.219-.51-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.093.172.187.129.323-.082.28-.18.552-.266.833-.055.179-.137.217-.329.14a5.526 5.526 0 01-1.736-1.18c-.857-.828-1.631-1.742-2.597-2.458a11.365 11.365 0 00-.689-.471c-.985-.957.13-1.743.388-1.836.27-.098.093-.432-.779-.428-.872.004-1.67.295-2.687.684a3.055 3.055 0 01-.465.137 9.597 9.597 0 00-2.883-.102c-1.885.21-3.39 1.102-4.497 2.623C.082 8.606-.231 10.684.152 12.85c.403 2.284 1.569 4.175 3.36 5.653 1.858 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.133-.284 4.994-1.86.47.234.962.327 1.78.397.63.059 1.236-.03 1.705-.128.735-.156.684-.837.419-.961-2.155-1.004-1.682-.595-2.113-.926 1.096-1.296 2.746-2.642 3.392-7.003.05-.347.007-.565 0-.845-.004-.17.035-.237.23-.256a4.173 4.173 0 001.545-.475c1.396-.763 1.96-2.015 2.093-3.517.02-.23-.004-.467-.247-.588zM11.581 18c-2.089-1.642-3.102-2.183-3.52-2.16-.392.024-.321.471-.235.763.09.288.207.486.371.739.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.167-1.361-.802-2.5-1.86-3.301-3.307-.774-1.393-1.224-2.887-1.298-4.482-.02-.386.093-.522.477-.592a4.696 4.696 0 011.529-.039c2.132.312 3.946 1.265 5.468 2.774.868.86 1.525 1.887 2.202 2.891.72 1.066 1.494 2.082 2.48 2.914.348.292.625.514.891.677-.802.09-2.14.11-3.054-.614zm1-6.44a.306.306 0 01.415-.287.302.302 0 01.2.288.306.306 0 01-.31.307.303.303 0 01-.304-.308zm3.11 1.596c-.2.081-.399.151-.59.16a1.245 1.245 0 01-.798-.254c-.274-.23-.47-.358-.552-.758a1.73 1.73 0 01.016-.588c.07-.327-.008-.537-.239-.727-.187-.156-.426-.199-.688-.199a.559.559 0 01-.254-.078c-.11-.054-.2-.19-.114-.358.028-.054.16-.186.192-.21.356-.202.767-.136 1.146.016.352.144.618.408 1.001.782.391.451.462.576.685.914.176.265.336.537.445.848.067.195-.019.354-.25.452z" fill="#4D6BFE"/></svg>`,
  gemini: `<svg viewBox="0 0 24 24"><path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 01-3.81-2.58 12.3 12.3 0 01-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 01-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81" fill="#4285f4"/></svg>`,
  qwen: `<svg viewBox="0 0 24 24"><defs><linearGradient id="qw" x1="0%" x2="100%" y1="0%" y2="0%"><stop offset="0%" stop-color="#6336E7" stop-opacity=".84"/><stop offset="100%" stop-color="#6F69F7" stop-opacity=".84"/></linearGradient></defs><path d="M12.604 1.34c.393.69.784 1.382 1.174 2.075a.18.18 0 00.157.091h5.552c.174 0 .322.11.446.327l1.454 2.57c.19.337.24.478.024.837-.26.43-.513.864-.76 1.3l-.367.658c-.106.196-.223.28-.04.512l2.652 4.637c.172.301.111.494-.043.77-.437.785-.882 1.564-1.335 2.34-.159.272-.352.375-.68.37-.777-.016-1.552-.01-2.327.016a.099.099 0 00-.081.05 575.097 575.097 0 01-2.705 4.74c-.169.293-.38.363-.725.364-.997.003-2.002.004-3.017.002a.537.537 0 01-.465-.271l-1.335-2.323a.09.09 0 00-.083-.049H4.982c-.285.03-.553-.001-.805-.092l-1.603-2.77a.543.543 0 01-.002-.54l1.207-2.12a.198.198 0 000-.197 550.951 550.951 0 01-1.875-3.272l-.79-1.395c-.16-.31-.173-.496.095-.965.465-.813.927-1.625 1.387-2.436.132-.234.304-.334.584-.335a338.3 338.3 0 012.589-.001.124.124 0 00.107-.063l2.806-4.895a.488.488 0 01.422-.246c.524-.001 1.053 0 1.583-.006L11.704 1c.341-.003.724.032.9.34zm-3.432.403a.06.06 0 00-.052.03L6.254 6.788a.157.157 0 01-.135.078H3.253c-.056 0-.07.025-.041.074l5.81 10.156c.025.042.013.062-.034.063l-2.795.015a.218.218 0 00-.2.116l-1.32 2.31c-.044.078-.021.118.068.118l5.716.008c.046 0 .08.02.104.061l1.403 2.454c.046.081.092.082.139 0l5.006-8.76.783-1.382a.055.055 0 01.096 0l1.424 2.53a.122.122 0 00.107.062l2.763-.02a.04.04 0 00.035-.02.041.041 0 000-.04l-2.9-5.086a.108.108 0 010-.113l.293-.507 1.12-1.977c.024-.041.012-.062-.035-.062H9.2c-.059 0-.073-.026-.043-.077l1.434-2.505a.107.107 0 000-.114L9.225 1.774a.06.06 0 00-.053-.031zm6.29 8.02c.046 0 .058.02.034.06l-.832 1.465-2.613 4.585a.056.056 0 01-.05.029.058.058 0 01-.05-.029L8.498 9.841c-.02-.034-.01-.052.028-.054l.216-.012 6.722-.012z" fill="url(#qw)"/></svg>`,
  volcengine_llm: `<svg viewBox="0 0 24 24"><path d="M19.44 10.153l-2.936 11.586a.215.215 0 00.214.261h5.87a.215.215 0 00.214-.261l-2.95-11.586a.214.214 0 00-.412 0zM3.28 12.778l-2.275 8.96A.214.214 0 001.22 22h4.532a.212.212 0 00.214-.165.214.214 0 000-.097l-2.276-8.96a.214.214 0 00-.41 0z" fill="#00E5E5"/><path d="M7.29 5.359L3.148 21.738a.215.215 0 00.203.261h8.29a.214.214 0 00.215-.261L7.7 5.358a.214.214 0 00-.41 0z" fill="#006EFF"/><path d="M14.44.15a.214.214 0 00-.41 0L8.366 21.739a.214.214 0 00.214.261H19.9a.216.216 0 00.171-.078.214.214 0 00.044-.183L14.439.15z" fill="#006EFF"/><path d="M10.278 7.741L6.685 21.736a.214.214 0 00.214.264h7.17a.215.215 0 00.214-.264L10.688 7.741a.214.214 0 00-.41 0z" fill="#00E5E5"/></svg>`,
  ollama: `<svg viewBox="0 0 24 24"><path d="M16.361 10.26a.894.894 0 00-.558.47l-.072.148.001.207c0 .193.004.217.059.353.076.193.152.312.291.448.24.238.51.3.872.205a.86.86 0 00.517-.436.752.752 0 00.08-.498c-.064-.453-.33-.782-.724-.897a1.06 1.06 0 00-.466 0zm-9.203.005c-.305.096-.533.32-.65.639a1.187 1.187 0 00-.06.52c.057.309.31.59.598.667.362.095.632.033.872-.205.14-.136.215-.255.291-.448.055-.136.059-.16.059-.353l.001-.207-.072-.148a.894.894 0 00-.565-.472 1.02 1.02 0 00-.474.007zm4.184 2c-.131.071-.223.25-.195.383.031.143.157.288.353.407.105.063.112.072.117.136.004.038-.01.146-.029.243-.02.094-.036.194-.036.222.002.074.07.195.143.253.064.052.076.054.255.059.164.005.198.001.264-.03.169-.082.212-.234.15-.525-.052-.243-.042-.28.087-.355.137-.08.281-.219.324-.314a.365.365 0 00-.175-.48.394.394 0 00-.181-.033c-.126 0-.207.03-.355.124l-.085.053-.053-.032c-.219-.13-.259-.145-.391-.143a.396.396 0 00-.193.032zm.39-2.195c-.373.036-.475.05-.654.086-.291.06-.68.195-.951.328-.94.46-1.589 1.226-1.787 2.114-.04.176-.045.234-.045.53 0 .294.005.357.043.524.264 1.16 1.332 2.017 2.714 2.173.3.033 1.596.033 1.896 0 1.11-.125 2.064-.727 2.493-1.571.114-.226.169-.372.22-.602.039-.167.044-.23.044-.523 0-.297-.005-.355-.045-.531-.288-1.29-1.539-2.304-3.072-2.497a6.873 6.873 0 00-.855-.031zm.645.937a3.283 3.283 0 011.44.514c.223.148.537.458.671.662.166.251.26.508.303.82.02.143.01.251-.043.482-.08.345-.332.705-.672.957a3.115 3.115 0 01-.689.348c-.382.122-.632.144-1.525.138-.582-.006-.686-.01-.853-.042-.57-.107-1.022-.334-1.35-.68-.264-.28-.385-.535-.45-.946-.03-.192.025-.509.137-.776.136-.326.488-.73.836-.963.403-.269.934-.46 1.422-.512.187-.02.586-.02.773-.002zm-5.503-11a1.653 1.653 0 00-.683.298C5.617.74 5.173 1.666 4.985 2.819c-.07.436-.119 1.04-.119 1.503 0 .544.064 1.24.155 1.721.02.107.031.202.023.208a8.12 8.12 0 01-.187.152 5.324 5.324 0 00-.949 1.02 5.49 5.49 0 00-.94 2.339 6.625 6.625 0 00-.023 1.357c.091.78.325 1.438.727 2.04l.13.195-.037.064c-.269.452-.498 1.105-.605 1.732-.084.496-.095.629-.095 1.294 0 .67.009.803.088 1.266.095.555.288 1.143.503 1.534.071.128.243.393.264.407.007.003-.014.067-.046.141a7.405 7.405 0 00-.548 1.873c-.062.417-.071.552-.071.991 0 .56.031.832.148 1.279L3.42 24h1.478l-.05-.091c-.297-.552-.325-1.575-.068-2.597.117-.472.25-.819.498-1.296l.148-.29v-.177c0-.165-.003-.184-.057-.293a.915.915 0 00-.194-.25 1.74 1.74 0 01-.385-.543c-.424-.92-.506-2.286-.208-3.451.124-.486.329-.918.544-1.154a.787.787 0 00.223-.531c0-.195-.07-.355-.224-.522a3.136 3.136 0 01-.817-1.729c-.14-.96.114-2.005.69-2.834.563-.814 1.353-1.336 2.237-1.475.199-.033.57-.028.776.01.226.04.367.028.512-.041.179-.085.268-.19.374-.431.093-.215.165-.333.36-.576.234-.29.46-.489.822-.729.413-.27.884-.467 1.352-.561.17-.035.25-.04.569-.04.319 0 .398.005.569.04a4.07 4.07 0 011.914.997c.117.109.398.457.488.602.034.057.095.177.132.267.105.241.195.346.374.43.14.068.286.082.503.045.343-.058.607-.053.943.016 1.144.23 2.14 1.173 2.581 2.437.385 1.108.276 2.267-.296 3.153-.097.15-.193.27-.333.419-.301.322-.301.722-.001 1.053.493.539.801 1.866.708 3.036-.062.772-.26 1.463-.533 1.854a2.096 2.096 0 01-.224.258.916.916 0 00-.194.25c-.054.109-.057.128-.057.293v.178l.148.29c.248.476.38.823.498 1.295.253 1.008.231 2.01-.059 2.581a.845.845 0 00-.044.098c0 .006.329.009.732.009h.73l.02-.074.036-.134c.019-.076.057-.3.088-.516.029-.217.029-1.016 0-1.258-.11-.875-.295-1.57-.597-2.226-.032-.074-.053-.138-.046-.141.008-.005.057-.074.108-.152.376-.569.607-1.284.724-2.228.031-.26.031-1.378 0-1.628-.083-.645-.182-1.082-.348-1.525a6.083 6.083 0 00-.329-.7l-.038-.064.131-.194c.402-.604.636-1.262.727-2.04a6.625 6.625 0 00-.024-1.358 5.512 5.512 0 00-.939-2.339 5.325 5.325 0 00-.95-1.02 8.097 8.097 0 01-.186-.152.692.692 0 01.023-.208c.208-1.087.201-2.443-.017-3.503-.19-.924-.535-1.658-.98-2.082-.354-.338-.716-.482-1.15-.455-.996.059-1.8 1.205-2.116 3.01a6.805 6.805 0 00-.097.726c0 .036-.007.066-.015.066a.96.96 0 01-.149-.078A4.857 4.857 0 0012 3.03c-.832 0-1.687.243-2.456.698a.958.958 0 01-.148.078c-.008 0-.015-.03-.015-.066a6.71 6.71 0 00-.097-.725C8.997 1.392 8.337.319 7.46.048a2.096 2.096 0 00-.585-.041zm.293 1.402c.248.197.523.759.682 1.388.03.113.06.244.069.292.007.047.026.152.041.233.067.365.098.76.102 1.24l.002.475-.12.175-.118.178h-.278c-.324 0-.646.041-.954.124l-.238.06c-.033.007-.038-.003-.057-.144a8.438 8.438 0 01.016-2.323c.124-.788.413-1.501.696-1.711.067-.05.079-.049.157.013zm9.825-.012c.17.126.358.46.498.888.28.854.36 2.028.212 3.145-.019.14-.024.151-.057.144l-.238-.06a3.693 3.693 0 00-.954-.124h-.278l-.119-.178-.119-.175.002-.474c.004-.669.066-1.19.214-1.772.157-.623.434-1.185.68-1.382.078-.062.09-.063.159-.012z" fill="#000"/></svg>`,
};

/* ── 服务商定义 ── */
const ASR_PROVIDERS = [
  {
    id: 'builtin_asr', name: '随口说语音识别模型', icon: 'suikoushuoa', color: '#0071e3',
    badge: '内置',
    builtin: true,
    fields: [],
  },
  {
    id: 'volcengine', name: '火山引擎', icon: 'volcengine', color: '#3370ff',
    fields: [
      { key: 'auth_method', label: '鉴权方式', type: 'select', options: [
        { value: 'app_key', label: 'App Key（新版控制台）' },
        { value: 'app_id_token', label: 'App ID + Token（旧版控制台）' },
      ]},
      { key: 'app_key', label: 'App Key', type: 'password', placeholder: '输入 App Key', showWhen: { auth_method: 'app_key' } },
      { key: 'app_id', label: 'App ID', type: 'text', placeholder: '输入 App ID', showWhen: { auth_method: 'app_id_token' } },
      { key: 'token', label: 'Access Token', type: 'password', placeholder: '输入 Access Token', showWhen: { auth_method: 'app_id_token' } },
      { key: 'resource_id', label: 'Resource ID', type: 'select', options: [
        { value: 'volc.seedasr.sauc.duration', label: 'volc.seedasr.sauc.duration' },
        { value: 'volc.seedasr.sauc.concurrent', label: 'volc.seedasr.sauc.concurrent' },
        { value: 'volc.bigasr.sauc.duration', label: 'volc.bigasr.sauc.duration' },
        { value: 'volc.bigasr.sauc.concurrent', label: 'volc.bigasr.sauc.concurrent' },
      ]},
    ],
    testable: true,
  },
  {
    id: 'aliyun_asr', name: '阿里云', icon: 'aliyun', color: '#ff6a00',
    fields: [
      { key: 'app_key', label: 'AppKey', type: 'password', placeholder: '输入 AppKey' },
      { key: 'access_key_id', label: 'AccessKey ID', type: 'text', placeholder: '输入 AccessKey ID' },
      { key: 'access_key_secret', label: 'AccessKey Secret', type: 'password', placeholder: '输入 AccessKey Secret' },
    ],
  },
  {
    id: 'sensevoice', name: 'SenseVoice Small', icon: 'sensevoice', color: '#8b5cf6', badge: '本地',
    fields: [
      { key: 'api_url', label: '服务地址', type: 'text', placeholder: 'http://localhost:8000' },
    ],
  },
  {
    id: 'custom_asr', name: '自定义 API', icon: 'custom', color: '#6b7280',
    fields: [
      { key: 'api_url', label: 'API 地址', type: 'text', placeholder: 'https://api.example.com/asr' },
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: '输入 API Key（可选）' },
    ],
  },
];

const LLM_PROVIDERS = [
  {
    id: 'openai', name: 'OpenAI', icon: 'openai', color: '#10a37f',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' },
      { key: 'api_url', label: 'API 地址', type: 'text', placeholder: 'https://api.openai.com/v1（默认）' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'gpt-4o' },
    ],
  },
  {
    id: 'claude', name: 'Claude', icon: 'claude', color: '#D4A27F',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-ant-...' },
      { key: 'api_url', label: 'API 地址', type: 'text', placeholder: 'https://api.anthropic.com（默认）' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'claude-sonnet-4-20250514' },
    ],
  },
  {
    id: 'deepseek', name: 'DeepSeek', icon: 'deepseek', color: '#4D6BFE',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'deepseek-chat' },
    ],
  },
  {
    id: 'gemini', name: 'Gemini', icon: 'gemini', color: '#4285f4',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: '输入 API Key' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'gemini-2.5-flash' },
    ],
  },
  {
    id: 'qwen', name: '通义千问', icon: 'qwen', color: '#6d28d9',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' },
      { key: 'api_url', label: 'API 地址', type: 'text', placeholder: 'https://dashscope.aliyuncs.com/compatible-mode/v1（默认）' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'qwen-plus' },
    ],
  },
  {
    id: 'volcengine_llm', name: '随口说大模型', icon: 'volcengine_llm', color: '#3370ff',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: '输入 API Key' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'openai/gpt-oss-120b' },
    ],
  },
  {
    id: 'ollama', name: 'Ollama', icon: 'ollama', color: '#1d1d1f', badge: '本地',
    fields: [
      { key: 'api_url', label: '服务地址', type: 'text', placeholder: 'http://localhost:11434（默认）' },
      { key: 'model', label: '模型', type: 'text', placeholder: 'llama3.2' },
    ],
  },
  {
    id: 'custom_llm', name: '自定义 API', icon: 'custom', color: '#6b7280',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: '输入 API Key' },
      { key: 'api_url', label: 'API 地址', type: 'text', placeholder: 'https://api.example.com/v1' },
      { key: 'model', label: '模型', type: 'text', placeholder: '输入模型名称' },
    ],
  },
];

/* 服务商配置数据（从 Python 加载） */
let providerConfigs = {};

/* ── 获取服务商 SVG 图标 ── */
function providerSvg(p) {
  return LOGO[p.icon] || LOGO.custom;
}

/* ── 渲染服务商卡片 ── */
let currentModalProvider = null;
let currentModalCategory = '';

function renderProviderGrid(containerId, providers, category) {
  const grid = document.getElementById(containerId);
  if (!grid) return;
  grid.innerHTML = providers.map(p => {
    const cfg = providerConfigs[p.id] || {};
    const isBuiltin = p.builtin || cfg._builtin || false;
    const isConfigured = isBuiltin || cfg._configured || false;
    const badgeHtml = (p.badge || cfg._builtin) ? `<span class="provider-badge builtin">${p.badge || '内置'}</span>` : '';
    const dotClass = isConfigured ? 'provider-status-dot active' : 'provider-status-dot';
    const action = isBuiltin ? '已就绪' : '点击配置';
    const onclick = isBuiltin ? '' : `onclick="openProviderModal('${p.id}','${category}')"`;

    return `<div class="provider-card ${isConfigured ? 'configured' : ''}" id="card-${p.id}" ${onclick}>
      <div class="provider-card-header">
        <div class="provider-icon" style="background:${p.color}12">${providerSvg(p)}</div>
        <div class="provider-card-info">
          <div class="provider-card-name">${p.name} ${badgeHtml}</div>
        </div>
        <div class="${dotClass}" id="dot-${p.id}"></div>
      </div>
      <div class="provider-card-action">
        <span>${action}</span>
        ${isBuiltin ? '' : '<span class="chevron">›</span>'}
      </div>
    </div>`;
  }).join('');
}

function findProvider(id) {
  return ASR_PROVIDERS.find(p => p.id === id) || LLM_PROVIDERS.find(p => p.id === id);
}

function openProviderModal(providerId, category) {
  const p = findProvider(providerId);
  if (!p) return;

  currentModalProvider = p;
  currentModalCategory = category;
  const cfg = providerConfigs[providerId] || {};
  const categoryLabel = category === 'asr' ? '语音识别服务商' : '大模型服务商';

  document.getElementById('modalIcon').style.cssText = `background:${p.color}12`;
  document.getElementById('modalIcon').innerHTML = providerSvg(p);
  document.getElementById('modalName').textContent = p.name + ' 设置';
  document.getElementById('modalCategory').textContent = categoryLabel;

  const isBuiltin = cfg._builtin;
  const body = document.getElementById('modalBody');
  if (isBuiltin) {
    body.innerHTML = '<div class="form-group"><p style="color:#86868b;font-size:13px;text-align:center;padding:12px 0">此服务已内置，可直接使用</p></div>';
  } else {
    body.innerHTML = p.fields.map(f => {
      const val = cfg[f.key] || '';
      const showWhen = f.showWhen ? `data-show-when='${JSON.stringify(f.showWhen)}'` : '';
      if (f.type === 'select') {
        const opts = f.options.map(o =>
          `<option value="${o.value}" ${val === o.value ? 'selected' : ''}>${o.label}</option>`
        ).join('');
        return `<div class="form-group" ${showWhen}>
          <label>${f.label}</label>
          <select data-field="${f.key}" onchange="applyModalShowWhen()">${opts}</select>
        </div>`;
      }
      return `<div class="form-group" ${showWhen}>
        <label>${f.label}</label>
        <input type="${f.type}" data-field="${f.key}" value="${escapeHtml(val)}" placeholder="${f.placeholder || ''}">
      </div>`;
    }).join('');
  }

  const testBtnContainer = document.getElementById('modalTestBtn');
  testBtnContainer.innerHTML = (!isBuiltin && p.testable)
    ? '<button class="btn btn-secondary" onclick="testModalProvider()">测试连接</button>' : '';

  document.getElementById('modalStatus').textContent = '';
  document.getElementById('modalStatus').className = 'form-status';

  const saveBtn = document.querySelector('#providerModal .form-actions .btn-primary');
  if (saveBtn) saveBtn.style.display = isBuiltin ? 'none' : '';

  document.getElementById('providerModal').classList.add('open');
  if (!isBuiltin) applyModalShowWhen();
}

function closeProviderModal() {
  document.getElementById('providerModal').classList.remove('open');
  currentModalProvider = null;
}

function applyModalShowWhen() {
  const body = document.getElementById('modalBody');
  body.querySelectorAll('[data-show-when]').forEach(el => {
    const cond = JSON.parse(el.dataset.showWhen);
    let visible = true;
    for (const [key, val] of Object.entries(cond)) {
      const input = body.querySelector(`[data-field="${key}"]`);
      if (input && input.value !== val) visible = false;
    }
    el.style.display = visible ? '' : 'none';
  });
}

function saveModalProvider() {
  if (!currentModalProvider) return;
  const body = document.getElementById('modalBody');
  const data = { id: currentModalProvider.id, category: currentModalCategory };
  body.querySelectorAll('[data-field]').forEach(el => {
    data[el.dataset.field] = el.value.trim();
  });

  const saveBtn = document.querySelector('.modal-footer .btn-primary');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = currentModalCategory === 'llm' ? '验证中…' : '保存中…';
  }
  showStatus('modalStatus', currentModalCategory === 'llm' ? '正在验证 API 连接…' : '', '');

  pyCall('save_provider', data);
}

function testModalProvider() {
  if (!currentModalProvider) return;
  const body = document.getElementById('modalBody');
  const data = { id: currentModalProvider.id };
  body.querySelectorAll('[data-field]').forEach(el => {
    data[el.dataset.field] = el.value.trim();
  });
  showStatus('modalStatus', '测试中…', '');
  pyCall('test_provider', data);
}

function onDefaultProviderChange() {
  const asr = document.getElementById('defaultAsrProvider').value;
  const llm = document.getElementById('defaultLlmProvider').value;
  const llmAgent = document.getElementById('defaultLlmAgentProvider').value;
  pyCall('save_defaults', { default_asr: asr, default_llm: llm, default_llm_agent: llmAgent });
}

function _buildLlmOptionsHtml(role) {
  let html = '<option value="">未配置</option>';
  LLM_PROVIDERS
    .filter(p => { const c = providerConfigs[p.id] || {}; return c._configured || c._builtin; })
    .forEach(p => {
      const cfg = providerConfigs[p.id] || {};
      let label;
      if (p.id === 'volcengine_llm') {
        label = role === 'agent' ? '随口说语音助手大模型' : '随口说语音输入大模型';
      } else {
        label = cfg.model || p.name;
      }
      html += `<optgroup label="${p.name}"><option value="${p.id}">${label}</option></optgroup>`;
    });
  return html;
}

function refreshDefaultSelectors() {
  const asrSel = document.getElementById('defaultAsrProvider');
  const llmSel = document.getElementById('defaultLlmProvider');
  const llmAgentSel = document.getElementById('defaultLlmAgentProvider');
  if (!asrSel || !llmSel) return;

  const currentAsr = asrSel.value;
  const currentLlm = llmSel.value;
  const currentLlmAgent = llmAgentSel ? llmAgentSel.value : '';

  let asrHtml = '';
  ASR_PROVIDERS
    .filter(p => p.builtin || (providerConfigs[p.id] || {})._configured)
    .forEach(p => {
      const cfg = providerConfigs[p.id] || {};
      const label = p.builtin ? p.name : (cfg.resource_id || cfg.model || p.name);
      asrHtml += `<optgroup label="${p.name}"><option value="${p.id}">${label}</option></optgroup>`;
    });
  asrSel.innerHTML = asrHtml || '<option value="">未配置</option>';
  asrSel.value = currentAsr;

  llmSel.innerHTML = _buildLlmOptionsHtml('input');
  llmSel.value = currentLlm;

  if (llmAgentSel) {
    llmAgentSel.innerHTML = _buildLlmOptionsHtml('agent');
    llmAgentSel.value = currentLlmAgent;
  }
}

function initModelPage() {
  renderProviderGrid('asrProviderGrid', ASR_PROVIDERS, 'asr');
  renderProviderGrid('llmProviderGrid', LLM_PROVIDERS, 'llm');
  refreshDefaultSelectors();
}

initModelPage();

/* ── 通用设置 ── */
function saveGeneralSettings() {
  const data = {
    auto_start: document.getElementById('autoStart').checked,
    auto_paste: document.getElementById('autoPaste').checked,
    show_float_window: document.getElementById('showFloatWindow').checked
  };
  pyCall('save_general', data);
}

/* ── 快捷键录制 ── */
let recordingHotkey = false;
let currentHotkeyName = '右 Command';

function startRecordHotkey() {
  const el = document.getElementById('hotkeyDisplay');
  const hint = el.querySelector('.hotkey-hint');
  if (recordingHotkey) return;
  recordingHotkey = true;
  el.classList.add('recording');
  document.getElementById('hotkeyText').textContent = '按下新的快捷键…';
  hint.textContent = 'ESC 取消';
  pyCall('start_hotkey_record', {});
}

function stopRecordHotkey(keyName) {
  recordingHotkey = false;
  const el = document.getElementById('hotkeyDisplay');
  el.classList.remove('recording');
  if (keyName) {
    currentHotkeyName = keyName;
  }
  document.getElementById('hotkeyText').textContent = currentHotkeyName;
  el.querySelector('.hotkey-hint').textContent = '点击修改';
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (document.getElementById('providerModal').classList.contains('open')) {
      closeProviderModal();
    } else if (recordingHotkey || obRecordingHotkey) {
      pyCall('cancel_hotkey_record', {});
      stopRecordHotkey(null);
      obOnHotkeyRecordDone(null);
    }
  }
});

document.getElementById('providerModal').addEventListener('click', (e) => {
  if (e.target.id === 'providerModal') closeProviderModal();
});

/* ── 技能设置 ── */
let customSkills = [];

function onSkillChanged() {
  const data = {
    auto_run: document.getElementById('skillsAutoRun').checked,
    personalize: document.getElementById('skillPersonalize').checked,
    personalize_text: document.getElementById('personalizeText').value,
    user_dict: document.getElementById('skillUserDict').checked,
    user_dict_text: document.getElementById('userDictText').value,
    auto_structure: document.getElementById('skillAutoStructure').checked,
    oral_filter: document.getElementById('skillOralFilter').checked,
    remove_trailing_punct: document.getElementById('skillRemovePunct').checked,
    custom_skills: collectCustomSkills(),
  };
  updateSkillsHint(data.auto_run);
  pyCall('save_skills', data);
}

function syncSkillsFromDOM() {
  document.querySelectorAll('.custom-skill-card').forEach(card => {
    const id = card.dataset.skillId;
    const skill = customSkills.find(s => s.id === id);
    if (skill) {
      skill.name = card.querySelector('.custom-skill-name').value.trim();
      skill.prompt = card.querySelector('.custom-skill-body textarea').value.trim();
      skill.enabled = card.querySelector('.custom-skill-toggle').checked;
    }
  });
}

function collectCustomSkills() {
  syncSkillsFromDOM();
  return customSkills.filter(s => s.name || s.prompt).map(s => ({
    id: s.id, name: s.name, prompt: s.prompt, enabled: s.enabled,
  }));
}

function addCustomSkill() {
  syncSkillsFromDOM();
  const id = 'cs_' + Date.now();
  customSkills.push({ id, name: '', prompt: '', enabled: true });
  renderCustomSkills();
  const card = document.querySelector(`[data-skill-id="${id}"]`);
  if (card) card.querySelector('.custom-skill-name').focus();
}

function deleteCustomSkill(id) {
  const skill = customSkills.find(s => s.id === id);
  const name = (skill && skill.name) || '未命名技能';
  showConfirm(`确定要删除「${name}」吗？`, () => {
    syncSkillsFromDOM();
    customSkills = customSkills.filter(s => s.id !== id);
    renderCustomSkills();
    onSkillChanged();
  });
}

function showConfirm(msg, onConfirm) {
  const overlay = document.createElement('div');
  overlay.className = 'confirm-overlay';
  overlay.innerHTML = `
    <div class="confirm-dialog">
      <div class="confirm-msg">${msg}</div>
      <div class="confirm-actions">
        <button class="btn-cancel">取消</button>
        <button class="btn-confirm-danger">删除</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  requestAnimationFrame(() => overlay.classList.add('visible'));

  const close = () => {
    overlay.classList.remove('visible');
    setTimeout(() => overlay.remove(), 150);
  };
  overlay.querySelector('.btn-cancel').onclick = close;
  overlay.querySelector('.btn-confirm-danger').onclick = () => { close(); onConfirm(); };
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
}

function renderCustomSkills() {
  const container = document.getElementById('customSkillsList');
  if (!container) return;
  container.innerHTML = customSkills.map(s => `
    <div class="custom-skill-card" data-skill-id="${s.id}">
      <div class="custom-skill-header">
        <input class="custom-skill-name" type="text" value="${escapeHtml(s.name)}"
               placeholder="技能名称" onchange="onSkillChanged()" onblur="onSkillChanged()">
        <label class="toggle">
          <input type="checkbox" class="custom-skill-toggle"
                 ${s.enabled ? 'checked' : ''} onchange="onSkillChanged()">
          <span class="toggle-slider"></span>
        </label>
        <button class="custom-skill-delete" onclick="deleteCustomSkill('${s.id}')" title="删除">✕</button>
      </div>
      <div class="custom-skill-body">
        <textarea placeholder="输入技能的 Prompt 指令，例如：&#10;将文本翻译为英文，保持原意不变。"
                  onchange="onSkillChanged()" onblur="onSkillChanged()">${escapeHtml(s.prompt)}</textarea>
      </div>
    </div>
  `).join('');
}

function updateSkillsHint(autoRun) {
  const el = document.getElementById('skillsHint');
  if (!el) return;
  el.textContent = autoRun
    ? '语音输入后，将自动执行已启用的技能处理文本'
    : '语音输入后，不调用大模型处理，也不执行任何技能';
}

/* ── 全屏引导 (Onboarding) ── */
let obStep = 0;
const OB_TOTAL = 5;
const OB_STORAGE_KEY = 'ob_done_v4';
let obDismissed = localStorage.getItem(OB_STORAGE_KEY) === '1';
let obTestPassed = false;

function checkShowGuide(settings) {
  const overlay = document.getElementById('onboardingOverlay');
  if (!overlay) return;

  obDismissed = localStorage.getItem(OB_STORAGE_KEY) === '1';
  if (obDismissed) {
    overlay.remove();
    return;
  }

  const providers = settings.providers || {};
  const hasExternalAsr = Object.entries(providers)
    .some(([id, p]) => id !== 'builtin_asr' && p._configured);
  const hasHistory = (settings._stats && settings._stats.total > 0);
  if (hasExternalAsr && hasHistory) {
    finishOnboarding();
    return;
  }

  overlay.style.display = 'flex';
  if (settings.hotkey_name) {
    document.querySelectorAll('#obHotkey, #obTestKeyName, #obStep4Key').forEach(el => {
      el.textContent = settings.hotkey_name;
    });
    obHighlightTargetKey(settings.hotkey_name);
  }
  renderObModelCards();
}

function renderObModelCards() {
  const container = document.getElementById('obModelCards');
  if (!container) return;
  const items = [
    { id: 'builtin_asr', name: '随口说', icon: 'suikoushuoa', active: true, badge: '内置' },
    { id: 'volcengine', name: '火山引擎', icon: 'volcengine' },
    { id: 'aliyun_asr', name: '阿里云', icon: 'aliyun' },
    { id: 'sensevoice', name: 'SenseVoice', icon: 'sensevoice', badge: '本地' },
  ];
  container.innerHTML = items.map((m, i) => {
    const svg = LOGO[m.icon] || LOGO.custom;
    const badge = m.badge ? `<span class="ob-card-badge">${m.badge}</span>` : '';
    return `<div class="ob-model-card ${m.active ? 'ob-m-active' : ''}" style="animation-delay:${i * 0.1}s">
      <div class="ob-model-logo-real">${svg}</div>
      <span>${m.name}</span>
      ${badge}
    </div>`;
  }).join('');
}

function obNext() {
  if (obStep < OB_TOTAL - 1) obGoTo(obStep + 1);
}

function obGoTo(step) {
  if (step === obStep || step < 0 || step >= OB_TOTAL) return;
  const slides = document.querySelectorAll('.ob-slide');
  const dots = document.querySelectorAll('.ob-dot');
  const goingForward = step > obStep;

  slides[obStep].classList.remove('active');
  slides[obStep].classList.add(goingForward ? 'exit-left' : '');

  obStep = step;

  slides.forEach((s, i) => {
    s.classList.remove('active', 'exit-left');
    if (i === obStep) s.classList.add('active');
  });
  dots.forEach((d, i) => d.classList.toggle('active', i === obStep));

  const fill = document.getElementById('obProgressFill');
  if (fill) fill.style.width = ((obStep + 1) / OB_TOTAL * 100) + '%';

  if (obStep === 4) {
    obStopAnimations();
    obCurrentScene = -1;
    obSwitchScene(0);
    setTimeout(() => obStartTypingAnim(), 500);
  } else {
    obStopAnimations();
  }
}

function finishOnboarding() {
  obDismissed = true;
  localStorage.setItem(OB_STORAGE_KEY, '1');
  const overlay = document.getElementById('onboardingOverlay');
  if (overlay) {
    overlay.classList.add('hidden');
    setTimeout(() => overlay.remove(), 500);
  }
}

/** 设置页：重新显示新手引导（须整页刷新以恢复已从 DOM 移除的遮罩） */
function resetOnboarding() {
  localStorage.removeItem(OB_STORAGE_KEY);
  obDismissed = false;
  location.reload();
}

function obHighlightTargetKey(hotkeyName) {
  document.querySelectorAll('.ob-key-target').forEach(k => k.classList.remove('ob-key-target'));
  const name = (hotkeyName || '').toLowerCase();
  let targetId = 'obKeyR';
  if (name.includes('左') || name.includes('left')) targetId = 'obKeyL';
  const el = document.getElementById(targetId);
  if (el) el.classList.add('ob-key-target');
}

function obOnHotkeyEvent(isDown) {
  document.querySelectorAll('.ob-key-target').forEach(k => {
    k.classList.toggle('ob-key-pressed', isDown);
  });
  if (isDown && obStep === 3 && !obTestPassed) {
    obTestPassed = true;
    const prompt = document.getElementById('obTestPrompt');
    if (prompt) {
      prompt.textContent = '快捷键正常工作！';
      prompt.classList.add('ob-test-success');
    }
  }
}

let obRecordingHotkey = false;

function obChangeHotkey() {
  if (obRecordingHotkey) return;
  obRecordingHotkey = true;
  const btn = document.querySelector('#obPermChangeBtn');
  if (btn) {
    btn.textContent = '按下新的快捷键… (ESC 取消)';
    btn.classList.add('ob-btn-recording');
  }
  pyCall('start_hotkey_record', {});
}

function obOnHotkeyRecordDone(keyName) {
  obRecordingHotkey = false;
  const btn = document.querySelector('#obPermChangeBtn');
  if (btn) {
    btn.textContent = '换个快捷键';
    btn.classList.remove('ob-btn-recording');
  }
  if (keyName) {
    document.querySelectorAll('#obHotkey, #obTestKeyName, #obStep4Key').forEach(el => {
      el.textContent = keyName;
    });
    obHighlightTargetKey(keyName);
  }
}

/* ── Feature carousel in Step 4 ── */
let obCurrentScene = 0;
let obTypingTimer = null;

const OB_SCENES = [
  {
    title: '语音输入',
    desc: '将光标放在任意输入框中，<strong>短按快捷键</strong>开始录音，再按一次结束。语音即刻转为文字，自动粘贴到光标处。',
    hint: '按下 <strong>{key}</strong> 按一次键，阅读下面的信息，然后按 <strong>{key}</strong> 键再次插入语音文本。',
    sample: '明天下午三点开会，记得带上季度报告。',
  },
  {
    title: '选中改写',
    desc: '选中一段文字后按下快捷键，说出改写指令（如"翻译成英文""精简一下"），AI 将直接替换原文。',
    hint: '先选中文本，再按 <strong>{key}</strong> 说出改写指令。',
    sample: '这个功能很好用我觉得非常不错推荐大家试试 → AI 改写为更通顺的表达',
  },
  {
    title: '选中提问',
    desc: '选中一段文字后按下快捷键，说出你的问题（如"这什么意思？""帮我分析一下"），AI 弹窗回答，不修改原文。',
    hint: '选中任意文字后按 <strong>{key}</strong> 提问，AI 弹窗回答。',
    sample: 'The quick brown fox jumps over the lazy dog → "这什么意思？"',
  },
  {
    title: '语音助手',
    desc: '无需选中文字，<strong>长按快捷键</strong>直接与 AI 对话。松手后 AI 会语音回答你的问题，适合快速查询和闲聊。',
    hint: '长按 <strong>{key}</strong> 说话，松手后 AI 语音回答。',
    sample: '今天天气怎么样？ / 帮我算一下 128 乘以 37',
  },
  {
    title: 'AI 技能',
    desc: '开启<strong>「技能自动运行」</strong>后，每次语音输入都会自动经过 AI 技能处理。内置口语过滤、自动结构化等技能，还可以创建自定义技能。',
    hint: '前往「技能」页面，打开<strong>自动运行</strong>开关，启用你需要的技能。',
    sample: '呃今天那个就是开会嘛讨论了一下方案 → 今天开会讨论了方案',
  },
  {
    title: '语音管理',
    desc: '<strong>长按快捷键</strong>对语音助手说<strong>「添加一个翻译技能」</strong>，AI 即刻创建并启用翻译技能。也可以说「打开口语过滤」「查看所有技能」等指令。',
    hint: '长按 <strong>{key}</strong> 说「添加一个翻译技能」，AI 自动完成。',
    sample: '「添加一个翻译技能」→ 已创建「翻译」技能并启用',
  },
];

function obSwitchScene(idx) {
  if (idx === obCurrentScene) return;
  obCurrentScene = idx;

  document.querySelectorAll('.ob-scene').forEach(s => {
    s.classList.toggle('active', +s.dataset.scene === idx);
  });
  document.querySelectorAll('.ob-scene-tab').forEach(t => {
    t.classList.toggle('active', +t.dataset.tab === idx);
  });

  const scene = OB_SCENES[idx];
  if (!scene) return;
  const keyName = currentHotkeyName || '右 Command';

  document.getElementById('obSceneTitle').textContent = scene.title;
  document.getElementById('obSceneText').innerHTML = scene.desc;

  const hintEl = document.getElementById('obStep4Hint');
  if (hintEl) {
    const icon = hintEl.querySelector('.ob-step4-hint-icon');
    const iconText = icon ? icon.outerHTML : '';
    hintEl.innerHTML = iconText + '<span>' + scene.hint.replace(/\{key\}/g, keyName) + '</span>';
  }

  const sampleEl = document.getElementById('obStep4Sample');
  if (sampleEl) sampleEl.innerHTML = '<em>' + scene.sample + '</em>';

  obStopAnimations();
  if (idx === 0) obStartTypingAnim();
  if (idx === 1) obStartRewriteAnim();
  if (idx === 2) obStartAskAnim();
}

function obStopAnimations() {
  if (obTypingTimer) { clearInterval(obTypingTimer); obTypingTimer = null; }
  document.querySelectorAll('.ob-anim-active').forEach(e => e.classList.remove('ob-anim-active'));
}

function obStartTypingAnim() {
  const line = document.getElementById('obTypingLine1');
  const float = document.getElementById('obFloatRec');
  if (!line || !float) return;

  const text = '明天下午三点开会，记得带上季度报告';
  let i = 0;
  line.textContent = '';
  float.classList.add('ob-anim-active');

  obTypingTimer = setInterval(() => {
    if (i < text.length) {
      line.textContent += text[i];
      i++;
    } else {
      clearInterval(obTypingTimer);
      obTypingTimer = null;
      float.classList.remove('ob-anim-active');
      setTimeout(() => { if (obCurrentScene === 0) obStartTypingAnim(); }, 2000);
    }
  }, 80);
}

function obStartRewriteAnim() {
  const selected = document.getElementById('obSelected');
  const result = document.getElementById('obRewriteResult');
  const float = document.getElementById('obFloatThink');
  if (!selected || !result || !float) return;

  selected.classList.remove('ob-highlight');
  result.classList.remove('ob-show');
  float.classList.remove('ob-anim-active');

  setTimeout(() => selected.classList.add('ob-highlight'), 400);
  setTimeout(() => float.classList.add('ob-anim-active'), 1000);
  setTimeout(() => {
    float.classList.remove('ob-anim-active');
    selected.classList.remove('ob-highlight');
    result.classList.add('ob-show');
  }, 2500);
  setTimeout(() => {
    if (obCurrentScene === 1) obStartRewriteAnim();
  }, 5500);
}

function obStartAskAnim() {
  const popup = document.getElementById('obAnswerPopup');
  if (!popup) return;

  popup.classList.remove('ob-popup-show');
  setTimeout(() => popup.classList.add('ob-popup-show'), 800);
  setTimeout(() => {
    popup.classList.remove('ob-popup-show');
    if (obCurrentScene === 2) setTimeout(() => obStartAskAnim(), 1000);
  }, 5000);
}

let _obPasteGuard = false;

function obUpdateTryArea(text) {
  const textarea = document.getElementById('obTryTextarea');
  const statusText = document.getElementById('obTryStatusText');
  const statusEl = document.getElementById('obTryStatus');
  if (!textarea) return;

  textarea.value = text;
  _obPasteGuard = true;
  setTimeout(() => { _obPasteGuard = false; }, 600);
  if (statusEl) statusEl.classList.remove('recording');
  if (statusText) statusText.textContent = '识别完成';
  setTimeout(() => {
    if (statusText) statusText.textContent = '就绪 — 等待语音输入';
  }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('obTryTextarea');
  if (ta) ta.addEventListener('paste', (e) => {
    if (_obPasteGuard) e.preventDefault();
  });
});

function obSetTryRecording(isRecording) {
  const statusEl = document.getElementById('obTryStatus');
  const statusText = document.getElementById('obTryStatusText');
  if (statusEl) statusEl.classList.toggle('recording', isRecording);
  if (statusText) statusText.textContent = isRecording ? '正在聆听...' : '就绪 — 等待语音输入';
}

function navigateTo(page) {
  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.page === page);
  });
  document.querySelectorAll('.page').forEach(p => {
    p.classList.toggle('active', p.id === 'page-' + page);
  });
}

/* ── 时间节省计算 ── */
function updateTimeSaved(totalChars) {
  const TYPING_CPM = 40;
  const VOICE_CPM = 150;
  const savedMinutes = totalChars * (1 / TYPING_CPM - 1 / VOICE_CPM);

  const el = document.getElementById('timeSavedValue');
  const detailEl = document.getElementById('timeSavedChars');
  if (!el) return;

  if (savedMinutes < 1) {
    el.textContent = Math.round(savedMinutes * 60) + ' 秒';
  } else if (savedMinutes < 60) {
    el.textContent = Math.round(savedMinutes) + ' 分钟';
  } else {
    const hours = Math.floor(savedMinutes / 60);
    const mins = Math.round(savedMinutes % 60);
    el.textContent = hours + ' 小时 ' + (mins > 0 ? mins + ' 分钟' : '');
  }

  if (detailEl) {
    detailEl.textContent = totalChars.toLocaleString();
  }
}

/* ── 历史记录 ── */
function clearHistory() {
  pyCall('clear_history', {});
  renderHistory([]);
}

function renderHistory(items) {
  const list = document.getElementById('historyList');
  if (!items || items.length === 0) {
    list.innerHTML = '<div class="empty-state">暂无识别记录</div>';
    return;
  }
  list.innerHTML = items.map((item, i) => `
    <div class="history-item" onclick="pyCall('repaste', {index: ${i}})">
      <span class="history-text">${escapeHtml(item.text)}</span>
      <span class="history-time">${item.time || ''}</span>
    </div>
  `).join('');
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

/* ── 状态提示 ── */
function showStatus(id, msg, cls) {
  let el = document.getElementById(id);
  if (!el) {
    const container = document.querySelector('.page.active .form-actions');
    if (container) {
      el = document.createElement('div');
      el.className = 'form-status';
      el.id = id;
      container.parentNode.insertBefore(el, container.nextSibling);
    } else {
      return;
    }
  }
  el.className = 'form-status ' + (cls || '');
  el.textContent = msg;
  setTimeout(() => { if (el) el.textContent = ''; }, 3000);
}

/* ── 被 Python 调用的函数 ── */
window.updateState = function(state) {
  if (state.status !== undefined) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    dot.className = 'status-indicator';
    if (state.status === 'recording') {
      dot.classList.add('recording');
      text.textContent = '录音中…';
      obOnHotkeyEvent(true);
      if (obStep === 4 && !obDismissed) obSetTryRecording(true);
    } else if (state.status === 'processing') {
      dot.classList.add('processing');
      text.textContent = '识别中…';
      if (obStep === 4 && !obDismissed) obSetTryRecording(false);
    } else {
      text.textContent = '就绪';
      obOnHotkeyEvent(false);
      if (obStep === 4 && !obDismissed) obSetTryRecording(false);
    }
  }

  if (state.stats) {
    document.getElementById('statTotal').textContent = state.stats.total || 0;
    document.getElementById('statToday').textContent = state.stats.today || 0;
    document.getElementById('statChars').textContent = state.stats.chars || 0;
    updateTimeSaved(state.stats.chars || 0);
  }

  if (state.history !== undefined) {
    renderHistory(state.history);
    if (obStep === 4 && !obDismissed && state.history && state.history.length > 0) {
      obUpdateTryArea(state.history[0].text);
    }
  }
};

window.updateConnectionStatus = function(ok, message) {
  const dot = document.querySelector('#connStatus .conn-dot');
  const text = document.getElementById('connText');
  if (dot && text) {
    dot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
    text.textContent = message;
  }
};

window.updateProviderTestResult = function(providerId, ok, message) {
  if (currentModalProvider && currentModalProvider.id === providerId) {
    showStatus('modalStatus', (ok ? '✅ ' : '❌ ') + message, ok ? 'ok' : 'err');
  }
  if (ok) {
    const dot = document.getElementById('dot-' + providerId);
    if (dot) dot.className = 'provider-status-dot active';
  }
};

window.loadSettings = function(settings) {
  if (settings.auto_start !== undefined) document.getElementById('autoStart').checked = settings.auto_start;
  if (settings.auto_paste !== undefined) document.getElementById('autoPaste').checked = settings.auto_paste;
  if (settings.show_float_window !== undefined) document.getElementById('showFloatWindow').checked = settings.show_float_window;
  if (settings.hotkey_name) {
    currentHotkeyName = settings.hotkey_name;
    document.getElementById('hotkeyText').textContent = settings.hotkey_name;
  }
  if (settings.providers) {
    providerConfigs = settings.providers;
    initModelPage();
  }
  if (settings.default_asr) {
    const el = document.getElementById('defaultAsrProvider');
    if (el) el.value = settings.default_asr;
  }
  if (settings.default_llm) {
    const el = document.getElementById('defaultLlmProvider');
    if (el) el.value = settings.default_llm;
  }
  if (settings.default_llm_agent) {
    const el = document.getElementById('defaultLlmAgentProvider');
    if (el) el.value = settings.default_llm_agent;
  }
  if (settings.skills) {
    const sk = settings.skills;
    document.getElementById('skillsAutoRun').checked = !!sk.auto_run;
    document.getElementById('skillPersonalize').checked = !!sk.personalize;
    document.getElementById('personalizeText').value = sk.personalize_text || '';
    document.getElementById('skillUserDict').checked = !!sk.user_dict;
    document.getElementById('userDictText').value = sk.user_dict_text || '';
    document.getElementById('skillAutoStructure').checked = !!sk.auto_structure;
    document.getElementById('skillOralFilter').checked = !!sk.oral_filter;
    document.getElementById('skillRemovePunct').checked = !!sk.remove_trailing_punct;
    customSkills = (sk.custom_skills || []).map(s => ({
      ...s,
      id: s.id || ('cs_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)),
    }));
    renderCustomSkills();
    updateSkillsHint(!!sk.auto_run);
  }

  checkShowGuide(settings);
};

window.onProviderSaveResult = function(providerId, ok, message) {
  const saveBtn = document.querySelector('.modal-footer .btn-primary');
  if (saveBtn) {
    saveBtn.disabled = false;
    saveBtn.textContent = '保存';
  }

  if (ok) {
    showStatus('modalStatus', '✅ ' + message, 'ok');
    const body = document.getElementById('modalBody');
    const data = {};
    body.querySelectorAll('[data-field]').forEach(el => {
      data[el.dataset.field] = el.value.trim();
    });
    providerConfigs[providerId] = { ...providerConfigs[providerId], ...data, _configured: true };

    const dot = document.getElementById('dot-' + providerId);
    if (dot) dot.className = 'provider-status-dot active';
    const card = document.getElementById('card-' + providerId);
    if (card) card.classList.add('configured');
    refreshDefaultSelectors();
  } else {
    showStatus('modalStatus', '❌ ' + message, 'err');
  }
};

window.onHotkeyRecorded = function(keyName) {
  stopRecordHotkey(keyName);
  obOnHotkeyRecordDone(keyName);
};

window.updateDeskclawStatus = function(ok, message) {
  const dot = document.getElementById('deskclawDot');
  const text = document.getElementById('deskclawStatusText');
  if (dot) dot.className = 'deskclaw-status-dot ' + (ok ? 'ok' : 'err');
  if (text) text.textContent = message;
};
