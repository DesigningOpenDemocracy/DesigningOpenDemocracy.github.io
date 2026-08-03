---
title: Australian Party Governance Comparison
template: project.html
status: active
contributors:
  - DOD
summary: "A living reference comparing Australian political parties on internal governance structure, external reform advocacy, and ideology — with international comparators. Uses the Accountability Framework's 'how people participate in governance' test across both internal practice and external advocacy."
concepts: [sortition, citizens-assembly, liquid-democracy]
---

A living reference that scores Australian political parties (and key international comparators) on three dimensions derived from DOD's [Accountability Framework](index.md): internal governance structure, external governance reform advocacy, and ideological position. Deliberately **not** a ranking of merit — [see why](/blog/posts/2026-08-03-party-governance-comparison/).

## Methodology

Each party is scored on three dimensions. Governance axes use a −10 to +10 centered scale: 0 = typical major-party status quo as of 2026 (faction-controlled internal structure, no position on external reform), negative = more centralised / opposed to reform, positive = more distributed / pro-reform. Ideology uses −10 to +10. Scores are approximate qualitative judgment, not a rubric calculation, and intended for relative comparison — not precision. They reflect **documented, sourced practice**, not platform statements alone. Updates welcome via PR.

### Internal governance (−10 to +10)

How do members control party decisions? Composite of: leadership selection method, candidate preselection, policy platform approval, minority faction rights, and structural accountability mechanisms (recall, term limits, checks on executive power). 0 = typical major-party structure as of 2026 (faction-controlled with some member input).

| Score | Description |
|---|---|
| −10 to −8 | Single-leader, no formal membership — party IS the leader |
| −7 to −5 | Leader-appointed — membership exists but leader controls everything |
| −4 to −2 | Narrow elite circle, membership is symbolic |
| −1 | Leader-dominated but with some elite input |
| 0 | Elite/faction-controlled with some member input (typical major party as of 2026) |
| 1–3 | One member, one vote — on paper, mixed or inconsistent practice |
| 4–5 | Genuine one member, one vote — competitive, with minority rights |
| 6–7 | Novel mechanisms alongside standard one member, one vote |
| 8–10 | Fully novel — sortition, liquid democracy, direct member control |

### External governance reform advocacy (−10 to +10)

Does the party work to change *how governance works* — electoral systems, transparency, anti-corruption, accountability mechanisms? Scored on documented, sustained advocacy with specific outcomes, not platform mentions. 0 = no position or indifferent.

| Score | Description |
|---|---|
| −10 to −8 | Dismantles — seeks to replace democracy with authoritarian rule |
| −7 to −5 | Undermines — attacks electoral integrity, accountability bodies, media |
| −4 to −2 | Opposes reform — blocks or weakens accountability mechanisms |
| −1 | Disfavours reform — publicly sceptical, controls damage |
| 0 | No position or indifferent |
| 1–3 | Platform mentions only, no documented action |
| 4–5 | Specific policy commitments, some legislative or campaign action |
| 6–7 | Sustained campaigns with documented outcomes on multiple fronts |
| 8–10 | Governance reform is a major platform pillar or the party's primary reason for existing |

### Reading the scores

A high score isn't necessarily better, a low score isn't necessarily worse — the numbers measure *depth*, not merit. The dated notes and sources below each party are where the real comparison lives. For examples and nuance see the [rescoring blog post](/blog/posts/2026-08-03-party-governance-comparison/).

### Left–Right (−10 to +10)

Standard political spectrum for rough orientation. −10 = far left (revolutionary socialist), −5 = social democratic, 0 = centre, +5 = conservative, +10 = far right.

### Parties scored

21 parties: 16 Australian (11 active, 5 historical) plus 5 international comparators (hidden by default on graphs 1 and 2 — use the toggle button). Full selection rationale is in the [rescoring blog post](/blog/posts/2026-08-03-party-governance-comparison/).

## Graphs

<div class="gov-charts">
  <div class="gov-chart-wrapper">
    <div class="gov-chart-header">
      <h3>1. Internal Governance vs. Ideology</h3>
      <button class="chart-intl-toggle-btn" id="toggle-intl-chart1" type="button" aria-pressed="false">Show international parties</button>
    </div>
    <p class="chart-hint">Where parties sit on the left–right spectrum vs. how deeply democratic their internal structures are. Shows Australian parties by default — international comparators (Podemos, Five Star Movement, Pirate Party Germany, Party for Freedom, Your Party) are hidden until toggled on.</p>
    <div class="chart-container">
      <canvas id="chart-left-right-internal"></canvas>
    </div>
    <p class="chart-hint chart-warning">⚠️ A high score isn't necessarily better — see <a href="#reading-the-scores-high-isnt-better">Reading the scores</a>.</p>
  </div>
  <div class="gov-chart-wrapper">
    <div class="gov-chart-header">
      <h3>2. External Reform Advocacy vs. Ideology</h3>
      <button class="chart-intl-toggle-btn" id="toggle-intl-chart2" type="button" aria-pressed="false">Show international parties</button>
    </div>
    <p class="chart-hint">Where parties sit on the left–right spectrum vs. how strongly they advocate for governance reform. Negative = opposes reform, 0 = indifferent, positive = advocates. Shows Australian parties by default — toggle to add international comparators.</p>
    <div class="chart-container">
      <canvas id="chart-left-right-external"></canvas>
    </div>
    <p class="chart-hint chart-warning">⚠️ A high score isn't necessarily better — see <a href="#reading-the-scores-high-isnt-better">Reading the scores</a>.</p>
  </div>
  <div class="gov-chart-wrapper">
    <div class="gov-chart-header">
      <h3>3. External Reform Advocacy vs. Internal Governance</h3>
      <button class="chart-intl-toggle-btn" id="toggle-intl-chart3" type="button" aria-pressed="false">Show international parties</button>
    </div>
    <p class="chart-hint">The framework's two halves mapped against each other. Top-right quadrant = parties that both practice and advocate governance reform. Top-left = prefigurative internal practice without external reformism. Bottom-right = external advocacy without deep internal democracy. Shows Australian parties by default — toggle to add international comparators.</p>
    <div class="chart-container">
      <canvas id="chart-internal-external"></canvas>
    </div>
    <p class="chart-hint chart-warning">⚠️ A high score isn't necessarily better — see <a href="#reading-the-scores-high-isnt-better">Reading the scores</a>.</p>
  </div>
</div>

<p class="chart-hint" id="gov-logo-credits"></p>

<div class="gov-chart-wrapper gov-timeline" id="gov-timeline-section">
  <h3>4. Score Changes Over Time</h3>
  <p class="chart-hint">Toggle parties to compare how internal and external governance scores shift across review cycles. Defaults to all active Australian parties. Charts collapse when nothing is selected.</p>
  <div class="timeline-pills" id="timeline-pills"></div>
  <div class="gov-timeline-charts" id="chart-timeline-container" style="display:none">
    <div>
      <p class="timeline-chart-label">Internal governance</p>
      <div class="chart-container">
        <canvas id="chart-timeline-internal"></canvas>
      </div>
    </div>
    <div>
      <p class="timeline-chart-label">External reform advocacy</p>
      <div class="chart-container">
        <canvas id="chart-timeline-external"></canvas>
      </div>
    </div>
  </div>
</div>

## Raw data

*Scores are live from the data file at build time. See column notes for per-party sourcing and methodology caveats.*

<table class="gov-data-table" id="gov-data-table">
  <thead>
    <tr>
      <th>Party</th>
      <th>Left→Right</th>
      <th>Internal</th>
      <th>External</th>
      <th>Notability</th>
      <th>Founded</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

## Scoring justification

This section is rendered entirely from [`party-governance.json`](/data/party-governance.json) — the same file that drives the graphs, Raw data table, and timeline charts — so there is no separate hand-written write-up to fall out of sync. Each party's `history` array is a dated audit trail: every time a score changed (or was reassessed), that entry carries its own note and source links for each of the three dimensions. To rescore a party or add a new assessment point, edit the data file directly — the justification *is* the data.

### Australian Labor Party
<div class="gov-justification-body" data-slug="labor"></div>

### Liberal Party / Coalition
<div class="gov-justification-body" data-slug="liberal"></div>

### Australian Greens
<div class="gov-justification-body" data-slug="greens"></div>

### Victorian Socialists
<div class="gov-justification-body" data-slug="victorian-socialists"></div>

### One Nation
<div class="gov-justification-body" data-slug="one-nation"></div>

### Jacqui Lambie Network
<div class="gov-justification-body" data-slug="jacqui-lambie-network"></div>

### Katter's Australian Party
<div class="gov-justification-body" data-slug="katter"></div>

### Libertarian Party
<div class="gov-justification-body" data-slug="libertarian"></div>

### Pirate Party Australia
<div class="gov-justification-body" data-slug="pirate-party"></div>

### Fusion Party
<div class="gov-justification-body" data-slug="fusion"></div>

### Australian Democrats
<div class="gov-justification-body" data-slug="australian-democrats"></div>

### Flux Party
<div class="gov-justification-body" data-slug="flux"></div>

### MiVote
<div class="gov-justification-body" data-slug="mivote"></div>

### Democratic Labor Party (1955–1978)
<div class="gov-justification-body" data-slug="dlp"></div>

### United Australia Party (1931–1945)
<div class="gov-justification-body" data-slug="uap-historical"></div>

### Australia Party (1969–1986)
<div class="gov-justification-body" data-slug="australia-party"></div>

### Your Party (UK)
<div class="gov-justification-body" data-slug="your-party"></div>

### Podemos (Spain)
<div class="gov-justification-body" data-slug="podemos"></div>

### Five Star Movement (Italy)
<div class="gov-justification-body" data-slug="five-star-movement"></div>

### Pirate Party Germany
<div class="gov-justification-body" data-slug="pirate-party-germany"></div>

### Party for Freedom (Netherlands)
<div class="gov-justification-body" data-slug="pvv"></div>

## Background

The [Accountability Framework](index.md) asks *"is this org working on how people participate in governance?"* — but the answer is not always yes/no. This page makes the ambiguity quantitative. [Full background](/blog/posts/2026-08-03-party-governance-comparison/#why-this-page-exists).

## Expanding the reference

Contributions welcome via PR:
- **Add a party:** Include sourced evidence for each score in the PR description
- **Rescore:** Provide new evidence for changed scores
- **Add international comparators:** Especially parties with novel governance mechanisms — Alternativet (Denmark) is a documented candidate not yet added; see the internal heartbeat research note <!-- ../../internal-heartbeat/2026-07-31-au-parties-democracy-reform-assessment.md --> for method
- **New graph dimensions:** Membership vs. governance depth, party age vs. mechanism novelty
- **Academic rigour:** This is qualitative scoring by design. Someone could build a rubric- or matrix-based methodology (weighted sub-factors, inter-rater calibration) on top of the same evidence — pull requests for that welcome

## See also

- [Accountability Framework](index.md) — the standard this reference operationalises
- Internal heartbeat: AU party democracy reform assessment <!-- ../../internal-heartbeat/2026-07-31-au-parties-democracy-reform-assessment.md --> — full sourcing (private, see repo)
- [Your Party](../../organisations/your-party.md) — international comparator (sortition-based internal governance)
- [Sortition](../../concepts/sortition.md) · [Liquid Democracy](../../concepts/liquid-democracy.md) · [Citizens' Assembly](../../concepts/citizens-assembly.md)

<style>
  /* Wider grid for charts + table, but keep content bounded */
  .md-grid { max-width: 1300px; }
</style>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script>
(function() {
  const DATA_URL = '/data/party-governance.json';

  // Hardcoded white/near-white — this site runs a single dark "slate"
  // palette with no light-mode toggle, so chart text and gridlines should
  // always read against a dark background. (Previously read theme colors
  // via CSS custom properties, but that was reported unreadable for at
  // least one viewer — hardcoding removes the dependency on those
  // resolving the way we expect.)
  const fgText = '#fff';
  const fgGrid = 'rgba(255,255,255,0.25)';

  const COLORS = {
    grid: fgGrid,
    zero: fgText,
    text: fgText
  };

  Chart.defaults.color = fgText;
  Chart.defaults.borderColor = fgGrid;

  const PARTY_GLYPHS = {
    labor:                  { initials: 'ALP',  color: '#e1393e' },
    liberal:                { initials: 'L/NP', color: '#0047ab' },
    greens:                 { initials: 'GRN',  color: '#39b54a' },
    'victorian-socialists': { initials: 'VS',   color: '#b51616' },
    'one-nation':           { initials: 'ON',   color: '#ff8c00' },
    'jacqui-lambie-network':{ initials: 'JLN',  color: '#008080' },
    katter:                 { initials: 'KAP',  color: '#8b4513' },
    libertarian:            { initials: 'LP',   color: '#169a90' },
    'pirate-party':         { initials: 'PPAU', color: '#9933cc' },
    fusion:                 { initials: 'FUS',  color: '#ff6f61' },
    'australian-democrats': { initials: 'AD',   color: '#daa520' },
    flux:                   { initials: 'FLX',  color: '#00bcd4' },
    mivote:                 { initials: 'MV',   color: '#ff5722' },
    dlp:                    { initials: 'DLP',  color: '#7b1fa2' },
    'uap-historical':       { initials: 'UAP',  color: '#5c6bc0' },
    'australia-party':      { initials: 'AP',   color: '#26a69a' },
    'your-party':           { initials: 'YP',   color: '#e91e8a' },
    podemos:                { initials: 'PDM',  color: '#6a2d8f' },
    'five-star-movement':   { initials: 'M5S',  color: '#ffcc00' },
    'pirate-party-germany': { initials: 'PPDE', color: '#ff6600' },
    pvv:                    { initials: 'PVV',  color: '#4a4a4a' }
  };

  function partyGlyph(party) {
    return PARTY_GLYPHS[party.slug] || { initials: party.slug.substring(0,3).toUpperCase(), color: '#999' };
  }

  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1,3), 16), g = parseInt(hex.slice(3,5), 16), b = parseInt(hex.slice(5,7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  // Loads each party's logo (if it has one) into an Image so the scatter
  // plugin can draw it; resolves regardless of success/failure so a bad
  // image never blocks rendering — the plugin falls back to the colored
  // initials badge whenever `p.logo.image` isn't set.
  function preloadLogos(parties) {
    return Promise.all(parties.map(function(p) {
      if (!p.logo || !p.logo.path) return Promise.resolve();
      return new Promise(function(resolve) {
        var img = new Image();
        img.onload = function() { p.logo.image = img; resolve(); };
        img.onerror = function() { resolve(); };
        img.src = p.logo.path;
      });
    }));
  }

  function drawLogoBadge(ctx, img, x, y, r) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.save();
    ctx.clip();
    // "Contain" fit (never crops) — a wordmark logo cut off at a circle's
    // edge reads worse than one left smaller with a little white margin.
    var iw = img.naturalWidth || 1, ih = img.naturalHeight || 1;
    var pad = 0.82;
    var scale = Math.min((r * 2 * pad) / iw, (r * 2 * pad) / ih);
    var w = iw * scale, h = ih * scale;
    ctx.drawImage(img, x - w / 2, y - h / 2, w, h);
    ctx.restore();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function drawInitialsBadge(ctx, g, x, y, r) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = g.color;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold ' + (g.initials.length > 3 ? 9 : 10) + 'px "Roboto", sans-serif';
    ctx.fillText(g.initials, x, y + 1);
  }

  function labelPlugin(parties) {
    return {
      id: 'partyLabels',
      afterDatasetDraw: function(chart, args) {
        var ctx = chart.ctx;
         var meta = args.meta;
         var p = parties[meta.index];
         var g = partyGlyph(p);
         ctx.textAlign = 'center';
         ctx.textBaseline = 'middle';
         meta.data.forEach(function(point) {
           if (!point || point.x == null) return;
           var x = point.x, y = point.y;
           var r = 10 + (p.notability || 3) + (g.initials.length > 3 ? 4 : 0);
           ctx.save();
           ctx.globalAlpha = p.status === 'deregistered' ? 0.35 : 0.92;
           if (p.logo && p.logo.image) {
             drawLogoBadge(ctx, p.logo.image, x, y, r);
           } else {
             drawInitialsBadge(ctx, g, x, y, r);
           }
          ctx.restore();
        });
      }
    };
  }

  let timelineCharts = { internal: null, external: null };
  let scatterCharts = {};

  function renderTable(parties) {
    const tbody = document.querySelector('#gov-data-table tbody');
    tbody.innerHTML = parties.map(p =>
      `<tr>
        <td><strong>${p.name}</strong> <small>${p.country}</small></td>
        <td>${p.left_right}</td>
        <td>${p.internal_governance}</td>
        <td>${p.external_reform}</td>
        <td>${p.notability || '—'}</td>
        <td>${p.founded}</td>
        <td>${p.status === 'deregistered' ? 'Deregistered' : 'Active'}</td>
      </tr>`
    ).join('');
  }

  function formatSignedScore(v) {
    if (v > 0) return '+' + v;
    if (v < 0) return '−' + Math.abs(v);
    return '' + v;
  }

  function sourceLinksHtml(sources) {
    if (!sources || !sources.length) return '';
    var links = sources.map(function(s) {
      return '<a href="' + s.url + '" target="_blank" rel="noopener">' + (s.label || s.url) + '</a>';
    }).join(', ');
    return ' <span class="gov-just-sources">' + (sources.length > 1 ? 'Sources: ' : 'Source: ') + links + '</span>';
  }

  function justificationDimHtml(label, note, sources) {
    if (!note) return '';
    return '<p class="gov-just-dim"><strong>' + label + ':</strong> ' + note + sourceLinksHtml(sources) + '</p>';
  }

  function renderLogoCredits(parties) {
    var el = document.getElementById('gov-logo-credits');
    if (!el) return;
    var withLogos = parties.filter(function(p) { return p.logo && p.logo.image; });
    if (!withLogos.length) return;
    var links = withLogos.map(function(p) {
      return '<a href="' + p.logo.source + '" target="_blank" rel="noopener">' + p.name + '</a> (' + p.logo.license + ')';
    });
    el.innerHTML = 'Party logos used across the graphs above (international parties appear once toggled on): ' + links.join(', ') + ' — via Wikimedia Commons. Parties without a freely licensed logo on file show initials instead.';
  }

  function renderJustification(parties) {
    document.querySelectorAll('.gov-justification-body').forEach(function(container) {
      var p = parties.find(function(x) { return x.slug === container.dataset.slug; });
      if (!p || !p.history || !p.history.length) return;
      var sorted = p.history.slice().sort(function(a, b) { return a.date.localeCompare(b.date); });
      var scoringNoteHtml = p.scoring_note ? '<p class="gov-just-scoring-note"><em>' + p.scoring_note + '</em></p>' : '';
      var entriesHtml = sorted.map(function(h) {
        var scoreLine = '<p class="gov-just-date"><strong>' + h.date + '</strong> — ' +
          'Left–Right ' + formatSignedScore(h.left_right) +
          ', Internal ' + h.internal_governance +
          ', External ' + formatSignedScore(h.external_reform) + '</p>';
        var dims = [
          justificationDimHtml('Left–Right', h.left_right_note, h.left_right_sources),
          justificationDimHtml('Internal', h.internal_note, h.internal_sources),
          justificationDimHtml('External', h.external_note, h.external_sources)
        ].join('');
        return '<div class="gov-just-entry">' + scoreLine + dims + '</div>';
      }).join('');
      container.innerHTML = scoringNoteHtml + entriesHtml;
    });
  }

  function renderScatter(canvasId, config) {
    if (scatterCharts[canvasId]) {
      scatterCharts[canvasId].destroy();
      scatterCharts[canvasId] = null;
    }
    const ctx = document.getElementById(canvasId).getContext('2d');
    scatterCharts[canvasId] = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: config.parties.map(p => {
          const g = partyGlyph(p);
          return {
            label: p.name + (p.country !== 'AU' ? ' (' + p.country + ')' : ''),
            data: [{ x: p[config.x], y: p[config.y] }],
            backgroundColor: 'transparent',
            borderColor: 'transparent',
            pointRadius: 16,
            pointHoverRadius: 20,
            borderWidth: 0
          };
        })
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: function(ctx) {
                const p = config.parties[ctx.datasetIndex];
                let lines = [p.name];
                if (p.country !== 'AU') lines.push('Country: ' + p.country);
                lines.push('Internal gov: ' + p.internal_governance);
                lines.push('External reform: ' + p.external_reform);
                if (p.notability) lines.push('Notability: ' + p.notability + '/10');
                if (p.note) lines.push(p.note.substring(0, 120) + (p.note.length > 120 ? '...' : ''));
                const latest = p.history && p.history.length
                  ? p.history.reduce((a, b) => (b.date > a.date ? b : a))
                  : null;
                if (latest) {
                  const allSources = (latest.internal_sources || []).concat(latest.external_sources || []);
                  if (allSources.length) lines.push('Source: ' + allSources[0].label);
                }
                return lines;
              }
            }
          },
          legend: { display: false }
        },
        scales: {
          x: {
            title: { display: true, text: config.xLabel, color: COLORS.text },
            grid: { color: function(ctx) {
              if (ctx.tick.value === 0) return COLORS.zero;
              return COLORS.grid;
            }},
            ...(config.xRange ? config.xRange : {})
          },
          y: {
            title: { display: true, text: config.yLabel, color: COLORS.text },
            ...(config.yRange ? config.yRange : {})
          }
        }
      },
      plugins: [labelPlugin(config.parties)]
    });
  }

  var TIMELINE_DIMENSIONS = [
    { key: 'internal', field: 'internal_governance', canvasId: 'chart-timeline-internal', yLabel: 'Internal governance score' },
    { key: 'external', field: 'external_reform', canvasId: 'chart-timeline-external', yLabel: 'External reform score' }
  ];

  function renderTimeline(parties, selected) {
    TIMELINE_DIMENSIONS.forEach(function(dim) {
      if (timelineCharts[dim.key]) { timelineCharts[dim.key].destroy(); timelineCharts[dim.key] = null; }
    });

    var container = document.getElementById('chart-timeline-container');
    if (!selected || selected.length === 0) {
      container.style.display = 'none';
      return;
    }
    container.style.display = '';

    var selectedParties = selected
      .map(function(slug) { return parties.find(function(x) { return x.slug === slug; }); })
      .filter(function(p) { return p && p.history && p.history.length > 0; });

    TIMELINE_DIMENSIONS.forEach(function(dim) {
      var datasets = selectedParties.map(function(p) {
        var sorted = p.history.slice().sort(function(a, b) { return a.date.localeCompare(b.date); });
        var g = partyGlyph(p);
        return {
          label: p.name,
          data: sorted.map(function(h) {
            return { x: h.date + '-01', y: h[dim.field], note: h[dim.key + '_note'], sources: h[dim.key + '_sources'] };
          }),
          borderColor: g.color,
          backgroundColor: hexToRgba(g.color, 0.10),
          borderWidth: 2.5,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.1
        };
      });

      var ctx = document.getElementById(dim.canvasId).getContext('2d');
      timelineCharts[dim.key] = new Chart(ctx, {
        type: 'line',
        data: { datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { intersect: false, mode: 'index' },
          plugins: {
            legend: {
              position: 'bottom',
              labels: { usePointStyle: true, boxWidth: 8, padding: 12, font: { size: 10 } }
            },
            tooltip: {
              callbacks: {
                label: function(ctx) {
                  var raw = ctx.raw;
                  var lines = [ctx.dataset.label + ': ' + raw.y];
                  if (raw.note) lines.push(raw.note.length > 140 ? raw.note.substring(0, 140) + '...' : raw.note);
                  if (raw.sources && raw.sources.length) lines.push('Source: ' + raw.sources[0].label);
                  return lines;
                }
              }
            }
          },
          scales: {
            x: {
              // Real time scale (not category) so the horizontal spacing
              // between points — and each party's line length — reflects
              // actual elapsed time, e.g. Labor's 1967-2026 span reads as
              // far longer than Your Party's single 2026 point.
              type: 'time',
              time: { tooltipFormat: 'yyyy-MM', displayFormats: { year: 'yyyy' } },
              title: { display: true, text: 'Date', color: COLORS.text }
            },
            y: {
              min: -10,
              max: 10,
              ticks: { stepSize: 2 },
              title: { display: true, text: dim.yLabel, color: COLORS.text }
            }
          }
        }
      });
    });
  }

  // Graph 1 & 2 show Australian parties only by default; international
  // comparators (Podemos, Five Star Movement, Pirate Party Germany, Party
  // for Freedom, Your Party) are opt-in via the toggle button next to each chart, so the
  // primary AU comparison isn't diluted unless a viewer asks for the
  // wider context.
  var SCATTER_CONFIGS = {};

  function setupIntlToggle(buttonId, canvasId, allParties) {
    var btn = document.getElementById(buttonId);
    if (!btn) return;
    var showIntl = false;

    btn.addEventListener('click', function() {
      showIntl = !showIntl;
      btn.classList.toggle('active', showIntl);
      btn.setAttribute('aria-pressed', String(showIntl));
      btn.textContent = showIntl ? 'Hide international parties' : 'Show international parties';
      var config = SCATTER_CONFIGS[canvasId];
      var parties = showIntl ? allParties : allParties.filter(function(p) { return p.country === 'AU'; });
      renderScatter(canvasId, Object.assign({}, config, { parties: parties }));
    });
  }

  function setupTimeline(parties) {
    var pillsEl = document.getElementById('timeline-pills');
    var DEFAULT_SELECTED = parties
      .filter(function(p) { return p.country === 'AU' && p.status === 'active'; })
      .map(function(p) { return p.slug; });
    var selected = DEFAULT_SELECTED.slice();

    parties.forEach(function(p) {
      var g = partyGlyph(p);
      var btn = document.createElement('button');
      btn.className = 'timeline-pill' + (selected.indexOf(p.slug) !== -1 ? ' active' : '');
      btn.dataset.slug = p.slug;
      btn.style.setProperty('--pill-color', g.color);
      btn.textContent = g.initials;
      btn.title = p.name + (p.country !== 'AU' ? ' (' + p.country + ')' : '');
      if (p.status === 'deregistered') btn.classList.add('deregistered');

      btn.addEventListener('click', function() {
        var idx = selected.indexOf(p.slug);
        if (idx === -1) { selected.push(p.slug); btn.classList.add('active'); }
        else { selected.splice(idx, 1); btn.classList.remove('active'); }
        renderTimeline(parties, selected);
      });

      pillsEl.appendChild(btn);
    });

    renderTimeline(parties, selected);
  }

  fetch(DATA_URL)
    .then(r => r.json())
    .then(data => preloadLogos(data.parties).then(() => data))
    .then(data => {
      const parties = data.parties;
      renderTable(parties);
      renderJustification(parties);
      renderLogoCredits(parties);

      const graphConfigs = data.graphs;
      const auParties = parties.filter(p => p.country === 'AU');

      SCATTER_CONFIGS['chart-left-right-internal'] = {
        x: graphConfigs[0].x_axis,
        y: graphConfigs[0].y_axis,
        xLabel: graphConfigs[0].x_label,
        yLabel: graphConfigs[0].y_label,
        xRange: { min: -10, max: 10 },
        yRange: { min: -10, max: 10 }
      };
      SCATTER_CONFIGS['chart-left-right-external'] = {
        x: graphConfigs[1].x_axis,
        y: graphConfigs[1].y_axis,
        xLabel: graphConfigs[1].x_label,
        yLabel: graphConfigs[1].y_label,
        xRange: { min: -10, max: 10 },
        yRange: { min: -10, max: 10 }
      };
      SCATTER_CONFIGS['chart-internal-external'] = {
        x: graphConfigs[2].x_axis,
        y: graphConfigs[2].y_axis,
        xLabel: graphConfigs[2].x_label,
        yLabel: graphConfigs[2].y_label,
        xRange: { min: -10, max: 10 },
        yRange: { min: -10, max: 10 }
      };

      renderScatter('chart-left-right-internal', Object.assign({ parties: auParties }, SCATTER_CONFIGS['chart-left-right-internal']));
      renderScatter('chart-left-right-external', Object.assign({ parties: auParties }, SCATTER_CONFIGS['chart-left-right-external']));
      renderScatter('chart-internal-external', Object.assign({ parties: auParties }, SCATTER_CONFIGS['chart-internal-external']));

      setupIntlToggle('toggle-intl-chart1', 'chart-left-right-internal', parties);
      setupIntlToggle('toggle-intl-chart2', 'chart-left-right-external', parties);
      setupIntlToggle('toggle-intl-chart3', 'chart-internal-external', parties);

      setupTimeline(parties);
    })
    .catch(err => {
      console.error('Failed to load party governance data:', err);
      const charts = document.querySelectorAll('.chart-container');
      charts.forEach(c => c.innerHTML = '<p style="color:#c00">Failed to load chart data.</p>');
    });
})();
</script>
