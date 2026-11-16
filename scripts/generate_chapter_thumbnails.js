const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9222;
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve(JSON.parse(d)));
    }).on('error', reject);
  });
}

class CDPClient {
  constructor(wsUrl) { this.wsUrl = wsUrl; this.msgId = 0; this.pending = new Map(); }
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = err => reject(err);
      this.ws.onmessage = ev => {
        const msg = JSON.parse(ev.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(msg.error);
          else resolve(msg.result);
        }
      };
    });
  }
  send(method, params = {}) {
    const id = ++this.msgId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expr) {
    const res = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    return res.result ? res.result.value : res;
  }
  close() { if (this.ws) this.ws.close(); }
}

// 15 Dynamic Camera Angle & Scene Presets for each Chapter Thumbnail
const SCENE_CONFIGS = [
  { s: 120, camDist: 4.8, camUp: 1.6, camSide: 1.8, fov: 52, desc: 'Ch01: Deep Night Mountain Chase (AE86 vs R32)' },
  { s: 260, camDist: 5.2, camUp: 1.4, camSide: -1.9, fov: 55, desc: 'Ch02: Rainy Touge Reflections' },
  { s: 380, camDist: 6.5, camUp: 2.2, camSide: 2.6, fov: 58, desc: 'Ch03: Night Uphill Valley Overlook' },
  { s: 180, camDist: 4.5, camUp: 1.5, camSide: -1.5, fov: 50, desc: 'Ch04: Early Dawn Blue Fog' },
  { s: 310, camDist: 5.5, camUp: 1.8, camSide: 2.2, fov: 56, desc: 'Ch05: Bright Noon Green Mountains' },
  { s: 420, camDist: 6.0, camUp: 2.0, camSide: -2.4, fov: 54, desc: 'Ch06: Golden Morning Sunrise Uphill' },
  { s: 220, camDist: 4.8, camUp: 1.7, camSide: 1.6, fov: 52, desc: 'Ch07: Misty Sea of Clouds & Crags' },
  { s: 340, camDist: 5.0, camUp: 1.6, camSide: -2.0, fov: 54, desc: 'Ch08: Autumn Red Leaves & Drift' },
  { s: 460, camDist: 5.8, camUp: 1.9, camSide: 2.5, fov: 56, desc: 'Ch09: Stormy Night Ridge Lightning' },
  { s: 290, camDist: 5.2, camUp: 1.6, camSide: -2.2, fov: 52, desc: 'Ch10: Fiery Sunset Mountain Pass' },
  { s: 510, camDist: 7.2, camUp: 2.4, camSide: 3.2, fov: 60, desc: 'Ch11: Quiet Lakeside Night Pass' },
  { s: 360, camDist: 4.8, camUp: 1.6, camSide: -1.8, fov: 52, desc: 'Ch12: Snowy Frozen Winter Downhill' },
  { s: 240, camDist: 4.2, camUp: 1.5, camSide: 1.9, fov: 50, desc: 'Ch13: Five Consecutive Hairpins Apex' },
  { s: 440, camDist: 6.5, camUp: 2.2, camSide: -2.8, fov: 58, desc: 'Ch14: Summit Duel Twilight Vista' },
  { s: 140, camDist: 5.0, camUp: 1.7, camSide: 2.0, fov: 54, desc: 'Ch15: Grand Prix Start Line & Bright Skies' }
];

async function generateAllThumbnails() {
  const chrome = spawn(CHROME_PATH, [
    `--remote-debugging-port=${PORT}`,
    '--headless=new',
    '--disable-gpu-sandbox',
    '--use-gl=angle',
    '--use-angle=d3d11',
    '--window-size=960,540',
    'about:blank'
  ]);

  const outputDir = path.join(__dirname, '..', 'assets', 'chapters');
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  try {
    let list = null;
    for (let i = 0; i < 20; i++) {
      await sleep(300);
      try { list = await fetchJson(`http://127.0.0.1:${PORT}/json/list`); if (list?.length) break; } catch(e){}
    }
    const client = new CDPClient(list[0].webSocketDebuggerUrl);
    await client.connect();
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Page.navigate', { url: 'http://127.0.0.1:8420/index.html' });
    await sleep(2500);

    for (let i = 0; i < 15; i++) {
      const cfg = SCENE_CONFIGS[i];
      console.log(`Rendering Thumbnail for Chapter ${i + 1} / 15: ${cfg.desc}...`);

      await client.eval(`
        new Promise((resolve) => {
          // Switch to RACE screen cleanly
          switchScreen('RACE');
          battle.countdownActive = false;
          selectedChapterIdx = ${i};

          // Apply chapter course & scenery
          applyChapterCourse(${i});
          applyChapterScenery(${i});

          // Position player & rival
          battle.s = ${cfg.s};
          battle.rivalS = ${cfg.s + 18.0};
          battle.speed = 25.0;
          battle.steerAngle = 0.15;
          updateTougeTransforms(0.016);
          updateTougeAtmosphere(0.016, 12.0);

          // Custom cinematic camera setup
          const ps = sampleSpline(battle.s);
          const pPos = playerCarRoot.position;
          const _f = ps.tangent.clone().normalize();
          const _u = ps.normal.clone().normalize();
          const _r = new THREE.Vector3().crossVectors(_f, _u).normalize();

          mainCam.fov = ${cfg.fov};
          mainCam.updateProjectionMatrix();

          mainCam.position.copy(pPos)
            .addScaledVector(_f, -${cfg.camDist})
            .addScaledVector(_u, ${cfg.camUp})
            .addScaledVector(_r, ${cfg.camSide});

          mainCam.up.copy(_u);
          mainCam.lookAt(pPos.clone().addScaledVector(_u, 0.9).addScaledVector(_f, 2.5));

          // Hide UI overlays for pristine 3D capture
          document.querySelectorAll('.screen-layer').forEach(el => el.style.opacity = '0');
          document.getElementById('screen-race-hud').style.display = 'none';

          // Force WebGL render
          renderer.render(scene, mainCam);
          setTimeout(resolve, 300);
        });
      `);

      const shot = await client.send('Page.captureScreenshot', {
        format: 'jpeg',
        quality: 90,
        clip: { x: 0, y: 0, width: 960, height: 540, scale: 0.5 } // 480x270 thumbnail
      });

      const fileName = `chapter_${String(i + 1).padStart(2, '0')}.jpg`;
      const filePath = path.join(outputDir, fileName);
      fs.writeFileSync(filePath, Buffer.from(shot.data, 'base64'));
      console.log(`  -> Saved ${fileName} (${fs.statSync(filePath).size} bytes)`);
    }

    console.log('All 15 Chapter Thumbnails successfully created!');
    client.close();
  } finally {
    chrome.kill();
  }
}

generateAllThumbnails().catch(e => console.error(e));
