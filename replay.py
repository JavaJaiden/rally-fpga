"""Export an actual Rally JSONL trace to a self-contained, clearly labeled replay."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path


def export(trace: Path, output: Path) -> None:
    raw = trace.read_bytes()
    records = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if not records:
        raise ValueError('trace is empty')
    labels = {r['backend'] for r in records}
    if len(labels) != 1:
        raise ValueError('mixed backends must not be presented as one experiment')
    label = labels.pop()
    rows = []
    for r in records:
        values = [r[k] for k in ('frame', 'x', 'y', 'paddle', 'move', 'hits', 'misses')]
        if any(not isinstance(v, int) for v in values):
            raise ValueError('trace coordinates and counters must be integers')
        rows.append(values + [bool(r['error']), r['status']])
    data = json.dumps(rows, separators=(',', ':')).replace('<', '\\u003c')
    digest = hashlib.sha256(raw).hexdigest()
    page = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rally experiment replay</title>
<style>
:root{color-scheme:dark;--bg:#0d1421;--panel:#172233;--line:#304058;--muted:#afbdd0;--accent:#a8e977}*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;max-width:1080px;margin:0 auto;padding:36px 28px 60px;color:#edf4ff;background:var(--bg)}nav{display:flex;justify-content:space-between;gap:20px;padding-bottom:20px;border-bottom:1px solid var(--line);font-size:12px;letter-spacing:.12em;color:var(--accent);font-weight:700}h1{font-size:clamp(34px,4.5vw,48px);line-height:1.06;letter-spacing:-.045em;margin:24px 0 12px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.1em;margin-top:32px;color:var(--accent)}.lede{color:var(--muted);max-width:760px;font-size:18px}.notice{border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:24px 0;font-size:13px;color:var(--muted)}.notice strong{color:var(--accent)}canvas{display:block;width:100%;max-width:720px;height:auto;background:#101b2a;border:1px solid var(--line);border-radius:14px}.controls{display:flex;gap:14px;align-items:center;margin:20px 0;flex-wrap:wrap}button,select{font:inherit;padding:9px 18px;border:1px solid var(--line);border-radius:7px}button{background:var(--accent);color:var(--bg);min-width:100px;cursor:pointer}select{background:var(--panel);color:#fff}input{flex:1;min-width:140px;accent-color:var(--accent)}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #fff;outline-offset:4px}pre{white-space:pre-wrap;background:var(--panel);border-radius:10px;padding:20px;color:var(--muted)}small{overflow-wrap:anywhere;color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid var(--line)}th{font-weight:500;color:var(--muted)}#fault{color:var(--accent)}.foot{color:var(--muted);font-size:14px;max-width:880px}@media(max-width:600px){body{padding:24px 16px}table{font-size:12px}td,th{padding:8px 4px}nav span:last-child{max-width:130px;text-align:right}}
</style>
<nav><span>RALLY / FPGA AUTOPLAY LAB</span><span>RECORDED CONTROLLER REPLAY</span></nav>
<h1>Rally: an external cheat lab</h1>
<p class="lede">An automatic paddle controller for our own Pong game. Watch recorded moves and see corrupted requests produce zero movement.</p>
<div class="notice"><strong>__LABEL__</strong><br>This page replays a retained trace. It does not execute FPGA hardware or a live game.</div>
<canvas id="game" width="720" height="480" aria-label="Recorded single-paddle Pong game"></canvas>
<div class="controls"><button id="play">Pause</button><input id="frame" aria-label="Frame" type="range" min="0" max="__MAX__" value="0">
<select id="speed" aria-label="Replay speed"><option value="1">1x</option><option value="2">2x</option><option value="4">4x</option></select></div>
<table><tr><th>Frame</th><th>Movement</th><th>Hits / misses</th><th>Frame validation</th></tr>
<tr><td id="n"></td><td id="move"></td><td id="score"></td><td id="fault"></td></tr></table>
<h2>Experiment boundary</h2>
<pre>Custom game -> state + sequence + CRC -> controller
Custom game <- bounded move + status  <- controller
Invalid or missing reply -> zero movement</pre>
<p class="foot">The backend label identifies how the trace was produced. This is a sandbox cheat for the included game; other games need their own supported state and control interfaces. Simulation does not establish board operation, and playback speed is not a latency measurement.</p>
<small>Trace: __NAME__<br>SHA-256: __SHA__</small>
<script>
'use strict';
const rows=__DATA__, canvas=document.getElementById('game'), c=canvas.getContext('2d');
const slider=document.getElementById('frame'), button=document.getElementById('play');
let index=0,playing=true,last=0;
function draw(){const r=rows[index];c.fillStyle='#101b2a';c.fillRect(0,0,720,480);
 c.strokeStyle='#203249';c.lineWidth=1;for(let y=24;y<480;y+=32){c.beginPath();c.moveTo(360,y);c.lineTo(360,y+14);c.stroke();}
 c.fillStyle='#7790ac';c.font='12px system-ui';c.fillText('EXTERNAL CONTROLLER',32,28);c.fillText('RECORDED GAME STATE',530,28);
 c.fillStyle=r[7]?'#ffb275':'#a8e977';c.fillRect(12,r[3]*480/1024-45,10,90);
 c.fillStyle='#f1f6ff';c.beginPath();c.arc(r[1]*720/1024,r[2]*480/1024,5,0,2*Math.PI);c.fill();
 slider.value=String(index);document.getElementById('n').textContent=r[0];
 document.getElementById('move').textContent=r[4];document.getElementById('score').textContent=r[5]+' / '+r[6];
 document.getElementById('fault').textContent=r[7]?'Rejected; movement suppressed':(r[8]?'Control disabled or invalid':'Accepted');}
button.onclick=()=>{playing=!playing;button.textContent=playing?'Pause':'Play';};
slider.oninput=()=>{index=Number(slider.value);draw();};
function tick(now){if(playing&&now-last>=1000/(60*Number(document.getElementById('speed').value))){
 if(index+1<rows.length){index++;draw();}else{playing=false;button.textContent='Replay';}last=now;}
 requestAnimationFrame(tick);}
button.addEventListener('click',()=>{if(index===rows.length-1&&playing){index=0;draw();}});
draw();requestAnimationFrame(tick);
</script></html>'''
    for key, value in {'LABEL': html.escape(label), 'MAX': str(len(rows)-1),
                       'NAME': html.escape(trace.name), 'SHA': digest, 'DATA': data}.items():
        page = page.replace('__' + key + '__', value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding='utf-8')
    print(f'Wrote {len(rows)} recorded frames to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, default=Path('out/rally.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('out/rally-replay.html'))
    args = parser.parse_args()
    export(args.trace, args.output)
