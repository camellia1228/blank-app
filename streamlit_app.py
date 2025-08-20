import streamlit as st
from streamlit.components.v1 import html

# ---------------------------
# App Meta
# ---------------------------
st.set_page_config(page_title="Jump Runner - Dino Style", page_icon="🎮", layout="centered")

st.title("🎮 점프 달리기")
st.caption("스페이스바 또는 ↑ 키로 점프! 장애물을 피해서 오래 달리면 점수가 올라갑니다. 죽으면 ▶️ Restart 버튼으로 즉시 재시작.")

# ---------------------------
# (선택) 세션 상태: 최고 점수 안내 문구만 표시
# * 본 예제는 게임 로직이 HTML5 Canvas 내부에서 동작하므로
#   Python <-> JS 간 점수 동기화 없이, 임베드된 게임 화면에서 점수가 표시됩니다.
# ---------------------------
if "hint_shown" not in st.session_state:
    st.session_state.hint_shown = True
    st.info("팁: 게임은 페이지 안의 캔버스에서 자체적으로 동작합니다. 점수와 재시작 버튼도 그 안에서 표시돼요.")

# ---------------------------
# HTML5 Canvas + JS 게임 코드
# - 외부 라이브러리 없이 동작
# - 점수 측정, 충돌 판정, 게임오버, 재시작 모두 포함
# ---------------------------
GAME_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body {
    margin: 0;
    background: #0f172a; /* slate-900 */
    color: #e2e8f0;      /* slate-200 */
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Noto Sans, Arial, sans-serif;
  }
  .wrap {
    display: grid;
    place-items: center;
    padding: 12px;
  }
  #game {
    background: #111827; /* gray-900 */
    border: 2px solid #334155; /* slate-600 */
    border-radius: 12px;
    display: block;
  }
  .hud {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-rows: auto 1fr auto;
    pointer-events: none;
  }
  .topbar {
    display: flex;
    justify-content: space-between;
    padding: 8px 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.6);
  }
  .center {
    display: grid;
    place-items: center;
  }
  .gameover {
    text-align: center;
    background: rgba(2,6,23,0.6);
    padding: 16px 22px;
    border-radius: 12px;
    border: 1px solid #334155;
    box-shadow: 0 10px 30px rgba(0,0,0,0.45);
  }
  .btn {
    pointer-events: auto;
    margin-top: 12px;
    padding: 10px 16px;
    border-radius: 10px;
    border: 1px solid #334155;
    background: #1e293b; /* slate-800 */
    color: #e2e8f0;
    font-weight: 700;
    cursor: pointer;
    transition: transform .06s ease;
  }
  .btn:active { transform: scale(0.98); }
  .hint {
    text-align: center;
    padding: 8px 0 0 0;
    opacity: .85;
    font-size: 12px;
  }
  .frame {
    position: relative;
    width: 720px;
    max-width: 95vw;
  }
</style>
</head>
<body>
  <div class="wrap">
    <div class="frame">
      <canvas id="game" width="720" height="260"></canvas>
      <div class="hud">
        <div class="topbar">
          <div id="score">Score: 0</div>
          <div id="speed">Speed: 6.0</div>
        </div>
        <div class="center">
          <div id="overlay" class="gameover" style="display:none;">
            <div style="font-size:22px; font-weight:800; margin-bottom:4px;">GAME OVER</div>
            <div id="final" style="margin-bottom:8px;">Your Score: 0</div>
            <button id="restart" class="btn">▶️ Restart</button>
            <div class="hint">Space / ↑ : Jump · R : Restart</div>
          </div>
        </div>
        <div></div>
      </div>
    </div>
    <div class="hint">모바일은 화면 탭으로 점프할 수 있어요.</div>
  </div>

<script>
(() => {
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');

  // ---------------------------
  // Game Constants
  // ---------------------------
  const WIDTH = canvas.width;
  const HEIGHT = canvas.height;
  const GROUND_Y = HEIGHT - 40;    // Ground baseline
  const GRAVITY = 0.55;
  const JUMP_VELOCITY = -10.5;
  const PLAYER = { x: 60, y: GROUND_Y - 40, w: 32, h: 40, vy: 0, grounded: true };
  const COLORS = {
    bg: '#111827',
    ground: '#1f2937',
    player: '#22d3ee', // cyan-400
    obstacle: '#f43f5e', // rose-500
    text: '#e2e8f0'
  };

  // Obstacles
  let obstacles = [];
  let spawnTimer = 0;
  let spawnInterval = 75;  // frames between spawns; will scale with speed

  // Game state
  let running = true;
  let score = 0;
  let speed = 6.0;         // pixels per frame; gradually increases
  let frame = 0;

  // UI
  const scoreEl = document.getElementById('score');
  const speedEl = document.getElementById('speed');
  const overlay = document.getElementById('overlay');
  const finalEl = document.getElementById('final');
  const restartBtn = document.getElementById('restart');

  // ---------------------------
  // Helpers
  // ---------------------------
  function resetGame() {
    obstacles = [];
    spawnTimer = 0;
    spawnInterval = 75;
    running = true;
    score = 0;
    speed = 6.0;
    frame = 0;
    PLAYER.y = GROUND_Y - PLAYER.h;
    PLAYER.vy = 0;
    PLAYER.grounded = true;
    overlay.style.display = 'none';
  }

  function rectsOverlap(a, b) {
    return !(a.x + a.w < b.x || a.x > b.x + b.w || a.y + a.h < b.y || a.y > b.y + b.h);
  }

  function spawnObstacle() {
    // Randomize obstacle height/width (like cacti variants)
    const h = 20 + Math.floor(Math.random() * 30);
    const w = 14 + Math.floor(Math.random() * 22);
    const y = GROUND_Y - h;
    obstacles.push({ x: WIDTH + 10, y, w, h });
  }

  function jump() {
    if (PLAYER.grounded && running) {
      PLAYER.vy = JUMP_VELOCITY;
      PLAYER.grounded = false;
    }
  }

  // ---------------------------
  // Input
  // ---------------------------
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' || e.code === 'ArrowUp') {
      e.preventDefault();
      jump();
    }
    if (e.code === 'KeyR') {
      e.preventDefault();
      if (!running) resetGame();
    }
  });
  // Mobile / click jump
  canvas.addEventListener('pointerdown', () => jump());
  restartBtn.addEventListener('click', () => resetGame());

  // ---------------------------
  // Game Loop
  // ---------------------------
  function update() {
    frame++;

    // Increase speed slowly (difficulty curve)
    speed += 0.0012;
    spawnInterval = Math.max(40, 75 - Math.floor((speed - 6) * 3));

    // Spawn logic
    spawnTimer++;
    if (spawnTimer >= spawnInterval) {
      spawnObstacle();
      spawnTimer = 0;
    }

    // Move obstacles
    obstacles.forEach(o => o.x -= speed);
    // Remove off-screen
    obstacles = obstacles.filter(o => o.x + o.w > -10);

    // Physics
    PLAYER.vy += GRAVITY;
    PLAYER.y += PLAYER.vy;
    if (PLAYER.y >= GROUND_Y - PLAYER.h) {
      PLAYER.y = GROUND_Y - PLAYER.h;
      PLAYER.vy = 0;
      PLAYER.grounded = true;
    }

    // Scoring: increase over time; bonus for passing obstacles
    score += 0.2 + (speed - 6) * 0.02;
    obstacles.forEach(o => {
      if (!o.passed && (o.x + o.w) < PLAYER.x) {
        o.passed = true;
        score += 5; // pass bonus
      }
    });

    // Collision check
    for (const o of obstacles) {
      if (rectsOverlap(PLAYER, o)) {
        running = false;
        break;
      }
    }

    // HUD
    scoreEl.textContent = 'Score: ' + Math.floor(score);
    speedEl.textContent = 'Speed: ' + (Math.round(speed * 10) / 10).toFixed(1);
  }

  function draw() {
    // Clear
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    // Ground
    ctx.fillStyle = COLORS.ground;
    ctx.fillRect(0, GROUND_Y, WIDTH, 4);

    // Player
    ctx.fillStyle = COLORS.player;
    ctx.fillRect(PLAYER.x, PLAYER.y, PLAYER.w, PLAYER.h);

    // Obstacles
    ctx.fillStyle = COLORS.obstacle;
    obstacles.forEach(o => {
      ctx.fillRect(o.x, o.y, o.w, o.h);
    });
  }

  function loop() {
    if (running) {
      update();
      draw();
      requestAnimationFrame(loop);
    } else {
      // Freeze frame, show overlay
      draw();
      finalEl.textContent = 'Your Score: ' + Math.floor(score);
      overlay.style.display = 'block';
    }
  }

  // Start
  resetGame();
  requestAnimationFrame(loop);
})();
</script>
</body>
</html>
"""

# ---------------------------
# Render the embedded game
# ---------------------------
html(GAME_HTML, height=360, scrolling=False)
