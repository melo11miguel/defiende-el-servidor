// Carro de rally (silueta extruida, decoración, alerón) y humo de llantas.
// Las medidas son las del simulador: largo 4.0 m, ancho 1.8 m, entre ejes 2.5 m.

import * as THREE from "three";
import { registrar } from "./texturas.js";

function texturaDecoracion() {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 256;
  const g = c.getContext("2d");
  const fondo = g.createLinearGradient(0, 0, 1024, 0);
  fondo.addColorStop(0, "#1e3a8a"); fondo.addColorStop(0.55, "#1d4ed8"); fondo.addColorStop(1, "#0f172a");
  g.fillStyle = fondo; g.fillRect(0, 0, 1024, 256);
  // Franja dorada diagonal
  g.fillStyle = "#d4a017";
  g.beginPath(); g.moveTo(0, 160); g.lineTo(1024, 90); g.lineTo(1024, 140); g.lineTo(0, 215); g.closePath(); g.fill();
  g.fillStyle = "#facc15";
  g.beginPath(); g.moveTo(0, 222); g.lineTo(1024, 148); g.lineTo(1024, 158); g.lineTo(0, 232); g.closePath(); g.fill();
  // Número y nombre
  g.fillStyle = "#f8fafc"; g.beginPath(); g.roundRect(430, 40, 150, 110, 14); g.fill();
  g.fillStyle = "#0f172a"; g.font = "900 92px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("24", 505, 100);
  g.font = "italic 900 46px Inter, Arial"; g.textAlign = "left";
  g.fillStyle = "#fde047"; g.fillText("AUTONOMOUS", 620, 70);
  g.fillStyle = "#f8fafc"; g.fillText("RALLY", 620, 118);
  g.font = "700 30px Inter, Arial"; g.fillStyle = "#cbd5e1"; g.fillText("MLOps · PPO", 80, 70);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// Carro básico (geometría simple): se muestra mientras carga el modelo realista
// o si no se puede descargar.
function crearCarroBasico({ largo: L, ancho: W, ejes }) {
  const grupo = new THREE.Group();

  // Silueta lateral (x a lo largo, y altura) extruida a lo ancho
  const s = new THREE.Shape();
  const perfil = [[-2.02, 0.32], [-2.04, 0.78], [-1.7, 0.92], [-1.25, 0.96], [-0.85, 1.36], [0.2, 1.4],
    [0.9, 1.0], [1.65, 0.86], [2.0, 0.66], [2.04, 0.36], [1.75, 0.26], [-1.8, 0.26]];
  s.moveTo(perfil[0][0] * L / 4, perfil[0][1]);
  for (const [x, y] of perfil.slice(1)) s.lineTo(x * L / 4, y);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: W - 0.16, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 3 });
  geo.translate(0, 0, -(W - 0.16) / 2);
  const pintura = new THREE.MeshPhysicalMaterial({
    map: texturaDecoracion(), metalness: 0.55, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.06,
  });
  // UV laterales: proyección del perfil para que la decoración se vea en los costados
  // (en el costado derecho se invierte u para que el texto no salga en espejo)
  const pos = geo.attributes.position, uv = geo.attributes.uv, nor = geo.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    const u0 = (pos.getX(i) + L / 2) / L;
    uv.setXY(i, nor.getZ(i) < -0.5 ? 1 - u0 : u0, (pos.getY(i) - 0.2) / 1.3);
  }
  const cuerpo = new THREE.Mesh(geo, pintura);
  cuerpo.castShadow = true;
  grupo.add(cuerpo);

  // Vidrios (un poco más afuera que la carrocería)
  const v = new THREE.Shape();
  const pv = [[-1.18, 0.98], [-0.82, 1.32], [0.18, 1.35], [0.84, 1.02]];
  v.moveTo(pv[0][0] * L / 4, pv[0][1]);
  for (const [x, y] of pv.slice(1)) v.lineTo(x * L / 4, y);
  v.closePath();
  const vidrio = new THREE.MeshPhysicalMaterial({ color: 0x0b1220, metalness: 0.4, roughness: 0.04, clearcoat: 1 });
  const gv = new THREE.ExtrudeGeometry(v, { depth: W - 0.02, bevelEnabled: false });
  gv.translate(0, 0.005, -(W - 0.02) / 2);
  grupo.add(new THREE.Mesh(gv, vidrio));

  const negro = new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 0.5, metalness: 0.3 });
  const dorado = new THREE.MeshStandardMaterial({ color: 0xc9a227, metalness: 0.9, roughness: 0.25 });
  const add = (g, mat, x, y, z, ry = 0) => { const m = new THREE.Mesh(g, mat); m.position.set(x, y, z); m.rotation.y = ry; m.castShadow = true; grupo.add(m); return m; };
  // Alerón trasero con soportes
  add(new THREE.BoxGeometry(0.42, 0.06, W + 0.1), negro, -L * 0.47, 1.42, 0);
  for (const z of [0.55, -0.55]) add(new THREE.BoxGeometry(0.12, 0.36, 0.06), negro, -L * 0.45, 1.22, z);
  for (const z of [W / 2 + 0.05, -W / 2 - 0.05]) add(new THREE.BoxGeometry(0.46, 0.3, 0.03), dorado, -L * 0.47, 1.36, z);
  // Toma de aire en el techo, espejos y parachoques
  add(new THREE.BoxGeometry(0.5, 0.12, 0.35), negro, -0.05, 1.46, 0);
  for (const z of [W / 2 + 0.1, -W / 2 - 0.1]) add(new THREE.BoxGeometry(0.16, 0.1, 0.12), negro, L * 0.2, 1.08, z);
  add(new THREE.BoxGeometry(0.18, 0.18, W + 0.08), negro, L / 2 + 0.02, 0.36, 0);
  add(new THREE.BoxGeometry(0.16, 0.2, W + 0.04), negro, -L / 2 - 0.02, 0.38, 0);
  // Guardafangos ensanchados
  for (const x of [ejes / 2, -ejes / 2]) for (const z of [W / 2, -W / 2]) {
    const arco = add(new THREE.CylinderGeometry(0.48, 0.48, 0.18, 16, 1, false, 0, Math.PI), negro, x, 0.42, z);
    arco.rotation.set(Math.PI / 2, 0, -Math.PI / 2);
  }

  // Luces
  const faroMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 3 });
  for (const z of [0.58, -0.58]) add(new THREE.BoxGeometry(0.06, 0.12, 0.34), faroMat, L / 2 + 0.03, 0.66, z);
  const luzFreno = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0xff1e1e, emissiveIntensity: 0.6 });
  for (const z of [0.62, -0.62]) add(new THREE.BoxGeometry(0.06, 0.1, 0.4), luzFreno, -L / 2 - 0.04, 0.74, z);

  // Ruedas: pivote (dirección) → giro (rodar) → llanta + rin dorado
  const ruedas = [];
  const geoLlanta = new THREE.CylinderGeometry(0.36, 0.36, 0.3, 28);
  const llanta = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.92 });
  // Ruedas metidas bajo la carrocería (antes sobresalían: el centro iba en el borde del carro)
  const zr = W / 2 - 0.17;
  for (const [x, z, delantera] of [[ejes / 2, zr, true], [ejes / 2, -zr, true], [-ejes / 2, zr, false], [-ejes / 2, -zr, false]]) {
    const pivote = new THREE.Group();
    pivote.position.set(x, 0.36, z);
    const giro = new THREE.Group();
    const l = new THREE.Mesh(geoLlanta, llanta);
    l.rotation.x = Math.PI / 2;
    l.castShadow = true;
    const rin = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.32, 10), dorado);
    rin.rotation.x = Math.PI / 2;
    for (let k = 0; k < 5; k++) {
      const rayo = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.36, 0.33), dorado);
      rayo.rotation.set(Math.PI / 2, (k * Math.PI * 2) / 5, 0);
      giro.add(rayo);
    }
    giro.add(l, rin);
    pivote.add(giro);
    grupo.add(pivote);
    ruedas.push({ pivote, giro, delantera });
  }

  const faro = new THREE.SpotLight(0xfff3c4, 0, 60, 0.45, 0.6, 1.2);
  faro.position.set(L / 2, 0.8, 0);
  faro.target.position.set(L / 2 + 10, 0, 0);
  grupo.add(faro, faro.target);
  return { grupo, ruedas, luzFreno, faro };
}

// ------------------------------------------------------------------ carro realista
// Modelo 3D de deportivo del ejemplo oficial de three.js ("webgl_materials_car",
// modelo de vicent091036). Se descarga del repositorio de three.js; no se guarda
// en este repo. Se le pone nuestra decoración: pintura azul y dorada, rines dorados
// y el número 24. Las medidas se ajustan a las del simulador (distancia entre ejes).
const BASE = "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r170/examples/models/gltf/";
const DRACO = "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/";
const AZUL = new THREE.Color(0x1a3fb8), AZUL_OSCURO = new THREE.Color(0x0b1d5c);
const DORADO = new THREE.Color(0xb8862b), FRANJA = new THREE.Color(0xffd23f);

function texturaNumero() {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 256;
  const g = c.getContext("2d");
  g.fillStyle = "rgba(248,250,252,0.96)";
  g.beginPath(); g.roundRect(8, 30, 200, 196, 26); g.fill();
  g.fillStyle = "#0b1d5c"; g.font = "900 150px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("24", 108, 134);
  g.textAlign = "left";
  g.font = "italic 900 62px Inter, Arial"; g.fillStyle = "#ffd23f"; g.fillText("AUTONOMOUS", 222, 104);
  g.fillStyle = "#f8fafc"; g.fillText("RALLY", 222, 170);
  g.font = "700 30px Inter, Arial"; g.fillStyle = "#cbd5e1"; g.fillText("MLOps · PPO", 226, 222);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  // La proyección de DecalGeometry invierte el eje horizontal: se voltea para que se lea bien
  t.wrapS = THREE.RepeatWrapping;
  t.repeat.x = -1;
  t.offset.x = 1;
  return t;
}

// Pinta la carrocería con colores por vértice según la posición en el carro:
// adelante y arriba azul, abajo y atrás dorado, con una franja amarilla entre ambos.
function pintarCarroceria(mesh, raiz) {
  const geo = mesh.geometry;
  const pos = geo.attributes.position;
  const m = new THREE.Matrix4().copy(raiz.matrixWorld).invert().multiply(mesh.matrixWorld);
  const v = new THREE.Vector3(), c = new THREE.Color(), col = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(m);  // x adelante, y arriba, z lateral
    const corte = -v.x * 0.33 + (0.78 - v.y) * 1.25;  // diagonal que sube hacia atrás
    const t = THREE.MathUtils.smoothstep(corte, 0.05, 0.35);
    c.copy(AZUL).lerp(AZUL_OSCURO, THREE.MathUtils.clamp((v.y - 0.9) * 1.6, 0, 1)).lerp(DORADO, t);
    if (Math.abs(corte - 0.2) < 0.035) c.copy(FRANJA);
    col.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
}

async function cargarModelo({ largo: L, ancho: W, ejes }, luzFreno, faro, calidad) {
  const [{ GLTFLoader }, { DRACOLoader }, { DecalGeometry }] = await Promise.all([
    import("three/addons/loaders/GLTFLoader.js"),
    import("three/addons/loaders/DRACOLoader.js"),
    import("three/addons/geometries/DecalGeometry.js"),
  ]);
  const draco = new DRACOLoader().setDecoderPath(DRACO);
  const gltf = await new GLTFLoader().setDRACOLoader(draco).loadAsync(BASE + "ferrari.glb");
  const modelo = gltf.scene;

  // Orientación y escala: el modelo mira hacia -z y tiene 2.65 m entre ejes.
  const raiz = new THREE.Group();          // marco del carro: x adelante, y arriba, z lateral
  const ajuste = new THREE.Group();
  const escala = ejes / 2.65;
  ajuste.rotation.y = -Math.PI / 2;        // -z del modelo -> +x del carro
  ajuste.scale.setScalar(escala);
  ajuste.position.x = 0.17 * escala;       // centra el punto medio entre ejes en el origen
  ajuste.add(modelo);
  raiz.add(ajuste);
  raiz.updateMatrixWorld(true);

  // Materiales
  // Pintura: en calidad alta, laca (clearcoat); en media/baja, metálico estándar (mucho más
  // barato en gráficos integrados y casi igual gracias al reflejo del cielo HDR).
  const pintura = calidad === "alta"
    ? new THREE.MeshPhysicalMaterial({ vertexColors: true, metalness: 0.75, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.04 })
    : new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.8, roughness: 0.22 });
  const dorado = new THREE.MeshStandardMaterial({ color: 0xc9a227, metalness: 1, roughness: 0.22 });
  // Vidrio oscuro semitransparente. Sin "transmission": eso obliga a dibujar toda la
  // escena una segunda vez en cada cuadro solo para el vidrio (era lo que más pesaba).
  const vidrio = new THREE.MeshStandardMaterial({ color: 0x0a0f1a, metalness: 0.6, roughness: 0.05,
    transparent: true, opacity: 0.82 });
  const faros = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 2.5 });
  modelo.traverse((o) => {
    if (!o.isMesh) return;
    const n = o.name;
    // Solo la carrocería y las llantas proyectan sombra (el interior, frenos y cromo no se notan)
    o.castShadow = n === "body" || n === "tire";
    o.receiveShadow = n === "body";
    if (n === "body") { pintarCarroceria(o, raiz); o.material = pintura; }
    else if (n.startsWith("rim_")) o.material = dorado;
    else if (n === "glass") o.material = vidrio;
    else if (n === "lights_red") o.material = luzFreno;  // la misma luz de freno que maneja el visor
    else if (n === "lights" || n === "leds") o.material = faros;
    else if (n === "yellow_trim") o.visible = false;  // escudo de la marca original: no se muestra
  });

  // Sombra de contacto bajo el carro (textura del mismo ejemplo)
  const ao = await new THREE.TextureLoader().loadAsync(BASE + "ferrari_ao.png");
  const sombra = new THREE.Mesh(new THREE.PlaneGeometry(0.655 * 4, 1.3 * 4),
    new THREE.MeshBasicMaterial({ map: ao, blending: THREE.MultiplyBlending, toneMapped: false,
      transparent: true, premultipliedAlpha: true }));
  sombra.rotation.x = -Math.PI / 2;
  sombra.position.y = 0.01;
  sombra.renderOrder = 2;
  modelo.add(sombra);

  // Número 24 en las dos puertas (calcomanía proyectada sobre la carrocería)
  const cuerpo = modelo.getObjectByName("body");
  const mapa = texturaNumero();
  const ray = new THREE.Raycaster();
  for (const lado of [1, -1]) {
    const desde = new THREE.Vector3(-0.3, 0.6, lado * 3), hacia = new THREE.Vector3(0, 0, -lado);
    ray.set(raiz.localToWorld(desde.clone()), hacia.transformDirection(raiz.matrixWorld));
    const hit = ray.intersectObject(cuerpo, false)[0];
    if (!hit) continue;
    const orient = new THREE.Euler().setFromRotationMatrix(
      new THREE.Matrix4().lookAt(hit.point, hit.point.clone().add(ray.ray.direction.clone().negate()), new THREE.Vector3(0, 1, 0)));
    const geo = new DecalGeometry(cuerpo, hit.point, orient, new THREE.Vector3(2.05, 1.0, 0.8));
    const decal = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      map: mapa, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4,
      metalness: 0.2, roughness: 0.25 }));
    raiz.attach(decal);
  }

  // Ruedas: cada una en un pivote (dirección) → giro (rodar), en el marco del carro
  const ruedas = [];
  for (const [nombre, delantera] of [["wheel_fl", true], ["wheel_fr", true], ["wheel_rl", false], ["wheel_rr", false]]) {
    const rueda = modelo.getObjectByName(nombre);
    if (!rueda) continue;
    const p = new THREE.Vector3();
    rueda.getWorldPosition(p);
    raiz.worldToLocal(p);
    const pivote = new THREE.Group(), giro = new THREE.Group();
    pivote.position.copy(p);
    pivote.add(giro);
    raiz.add(pivote);
    raiz.updateMatrixWorld(true);
    giro.attach(rueda);
    ruedas.push({ pivote, giro, delantera });
  }

  faro.position.set(L / 2, 0.65, 0);
  faro.target.position.set(L / 2 + 10, 0, 0);
  return { raiz, ruedas };
}

// Devuelve el carro básico de inmediato y lo cambia por el realista cuando termina
// de cargar. `alCargar(ruedas)` avisa al visor que ahora hay otras ruedas que animar.
export function crearCarro(medidas, { alCargar, calidad = "media" } = {}) {
  const basico = crearCarroBasico(medidas);
  const grupo = new THREE.Group();
  grupo.add(basico.grupo);
  basico.grupo.remove(basico.faro, basico.faro.target);
  grupo.add(basico.faro, basico.faro.target);
  registrar("carro 3D", cargarModelo(medidas, basico.luzFreno, basico.faro, calidad))
    .then(({ raiz, ruedas }) => {
      grupo.remove(basico.grupo);
      grupo.add(raiz);
      if (alCargar) alCargar(ruedas);
    })
    .catch((e) => console.warn("No se pudo cargar el carro realista; se usa el básico.", e));
  return { grupo, ruedas: basico.ruedas, luzFreno: basico.luzFreno, faro: basico.faro };
}

// ------------------------------------------------------------------ humo y rocío
// Volutas de humo con textura de ruido que giran, crecen y se disipan. Con lluvia,
// las llantas levantan rocío de agua (más claro, rápido y bajo).
function texturaHumo() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  for (let k = 0; k < 26; k++) {           // varias bocanadas superpuestas = voluta irregular
    const x = 64 + (Math.random() - 0.5) * 50, y = 64 + (Math.random() - 0.5) * 50, r = 14 + Math.random() * 26;
    const grad = g.createRadialGradient(x, y, 0, x, y, r);
    grad.addColorStop(0, `rgba(255,255,255,${0.16 + Math.random() * 0.12})`);
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  }
  const borde = g.createRadialGradient(64, 64, 30, 64, 64, 64);   // se apaga hacia el borde
  borde.addColorStop(0, "rgba(0,0,0,0)"); borde.addColorStop(1, "rgba(0,0,0,1)");
  g.globalCompositeOperation = "destination-out"; g.fillStyle = borde; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export function crearHumo(scene, N = 900) {
  const pos = new Float32Array(N * 3), tam = new Float32Array(N), alfa = new Float32Array(N), giro = new Float32Array(N);
  const vel = new Float32Array(N * 3), vida = new Float32Array(N), vgiro = new Float32Array(N);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("tam", new THREE.BufferAttribute(tam, 1));
  geo.setAttribute("alfa", new THREE.BufferAttribute(alfa, 1));
  geo.setAttribute("giro", new THREE.BufferAttribute(giro, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { mapa: { value: texturaHumo() }, color: { value: new THREE.Color(0xd9d4cc) } },
    vertexShader: `attribute float tam; attribute float alfa; attribute float giro; varying float vA; varying float vG;
      void main(){ vA = alfa; vG = giro; vec4 mv = modelViewMatrix * vec4(position,1.0);
      gl_PointSize = tam * 420.0 / -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D mapa; uniform vec3 color; varying float vA; varying float vG;
      void main(){
        vec2 p = gl_PointCoord - 0.5; float c = cos(vG), s = sin(vG);
        vec4 t = texture2D(mapa, vec2(c * p.x - s * p.y, s * p.x + c * p.y) + 0.5);
        // un poco más oscuro abajo, como el humo real iluminado desde arriba
        gl_FragColor = vec4(color * (0.82 + 0.18 * (1.0 - gl_PointCoord.y)), t.a * vA);
      }`,
    transparent: true, depthWrite: false,
  });
  const puntos = new THREE.Points(geo, mat);
  puntos.frustumCulled = false;
  scene.add(puntos);
  let k = 0, rocio = false;

  function emitir(p, intensidad) {
    const n = Math.ceil(intensidad * (rocio ? 4 : 3));
    for (let j = 0; j < n; j++) {
      const i = k++ % N;
      pos[i * 3] = p.x + (Math.random() - 0.5) * 0.5; pos[i * 3 + 1] = 0.2; pos[i * 3 + 2] = p.z + (Math.random() - 0.5) * 0.5;
      const sube = rocio ? 0.5 + Math.random() * 0.6 : 0.7 + Math.random() * 1.0;
      vel[i * 3] = (Math.random() - 0.5) * 1.6; vel[i * 3 + 1] = sube; vel[i * 3 + 2] = (Math.random() - 0.5) * 1.6;
      vida[i] = 1; tam[i] = rocio ? 0.35 + Math.random() * 0.3 : 0.6 + Math.random() * 0.5;
      alfa[i] = (rocio ? 0.22 : 0.4) * intensidad + 0.12;
      giro[i] = Math.random() * 6.28; vgiro[i] = (Math.random() - 0.5) * 1.5;
    }
  }

  function actualizar(dt) {
    for (let i = 0; i < N; i++) {
      if (vida[i] <= 0) { alfa[i] = 0; continue; }
      vida[i] -= dt * (rocio ? 0.9 : 0.4);
      vel[i * 3 + 1] *= 1 - dt * 0.6;                 // el humo frena al subir
      pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
      tam[i] += dt * (rocio ? 1.6 : 2.4);
      giro[i] += vgiro[i] * dt;
      alfa[i] = Math.max(0, alfa[i] - dt * (rocio ? 0.45 : 0.22));
    }
    for (const a of ["position", "tam", "alfa", "giro"]) geo.attributes[a].needsUpdate = true;
  }

  // Con lluvia: rocío blanco azulado; en seco: humo de llanta gris claro
  function clima(mojado) {
    rocio = mojado;
    mat.uniforms.color.value.set(mojado ? 0xdfe6ee : 0xd9d4cc);
  }
  return { emitir, actualizar, clima, puntos };
}
