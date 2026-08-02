---
title: Australian Party Governance Comparison
template: project.html
status: active
contributors:
  - DOD
summary: "A living reference comparing Australian political parties on internal governance structure, external reform advocacy, and ideology — with international comparators. Uses the Accountability Framework's 'how people participate in governance' test across both internal practice and external advocacy."
concepts: [sortition, citizens-assembly, liquid-democracy]
---

A living reference that scores Australian political parties (and key international comparators) on three dimensions derived from DOD's [Accountability Framework](index.md): internal governance structure, external governance reform advocacy, and ideological position. The purpose is to make the framework's "how people participate in governance" test concrete and comparable — and to surface patterns the text of the framework alone cannot.

It is deliberately **not** a ranking of merit. A party with high internal democracy but zero external reform advocacy (prefigurative practice) tells a different story than one with strong external advocacy but weak internal structure (reform-from-outside), and the framework's current formulation does not resolve which qualifies more strongly — or whether both do. This document makes that visible rather than burying it in prose.

## Methodology

Each party is scored on three dimensions, 0–10 scale for governance axes, −10 to +10 for ideology. Scores are approximate and intended for relative comparison, not precision. They reflect **documented, sourced practice** — not platform statements alone — and are updated as new evidence surfaces. Additions and rescoring are welcome via PR.

### Internal governance (0–10)

How do members control party decisions? Composite of: leadership selection method, candidate preselection, policy platform approval, minority faction rights, and structural accountability mechanisms (recall, term limits, checks on executive power).

| Score | Description |
|---|---|
| 0–1 | Leader-appointed, no meaningful member input |
| 2–3 | Some member input but elite/faction-controlled in practice |
| 4–5 | OMOV on paper, mixed or inconsistent practice |
| 6–7 | Genuine OMOV with documented competitive practice and minority rights |
| 8–9 | Novel democratic mechanisms beyond standard OMOV: sortition, liquid democracy, deliberative structures |
| 10 | Full member control of all decisions through direct/liquid/sortition-based mechanisms |

### External governance reform advocacy (0–10)

Does the party work to change *how governance works* — electoral systems, transparency, anti-corruption, accountability mechanisms? Scored on documented, sustained advocacy with specific outcomes, not platform mentions.

| Score | Description |
|---|---|
| 0 | None, or actively opposes governance reform |
| 1–3 | Platform mentions only, no documented action |
| 4–5 | Specific policy commitments, some legislative or campaign action |
| 6–7 | Sustained campaigns with documented outcomes on multiple fronts |
| 8–9 | Governance reform is a major platform pillar with extensive record |
| 10 | Democracy reform is the party's primary reason for existing |

### Left–Right (−10 to +10)

Standard political spectrum for rough orientation. −10 = far left (revolutionary socialist), −5 = social democratic, 0 = centre, +5 = conservative, +10 = far right.

### Parties scored

11 Australian parties (active, except Flux and MiVote, both included for historical comparison of governance innovation despite deregistration) plus 1 international comparator. Selection: all parties assessed in the internal heartbeat AU party audit <!-- see ../../internal-heartbeat/2026-07-31-au-parties-democracy-reform-assessment.md --> with sufficient documentation. Additional international comparators (Podemos, M5S, German Pirate Party, Alternativet) are candidates for future scoring pending independent verification.

## Graphs

<div class="gov-charts">
  <div class="gov-chart-wrapper">
    <h3>1. Internal Governance vs. Ideology</h3>
    <p class="chart-hint">Where parties sit on the left–right spectrum vs. how deeply democratic their internal structures are.</p>
    <div class="chart-container">
      <canvas id="chart-left-right-internal"></canvas>
    </div>
  </div>
  <div class="gov-chart-wrapper">
    <h3>2. External Reform Advocacy vs. Internal Governance</h3>
    <p class="chart-hint">The framework's two halves mapped against each other. Top-right quadrant = parties that both practice and advocate governance reform. Top-left = prefigurative internal practice without external reformism. Bottom-right = external advocacy without deep internal democracy.</p>
    <div class="chart-container">
      <canvas id="chart-internal-external"></canvas>
    </div>
  </div>
</div>

<div class="gov-chart-wrapper gov-timeline" id="gov-timeline-section">
  <h3>3. Score Changes Over Time</h3>
  <p class="chart-hint">Toggle parties to compare how internal and external governance scores shift across review cycles. Default shows the three parties that best illustrate the framework's internal-vs-external distinction. Charts collapse when nothing is selected.</p>
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

Each party's scores, the evidence behind them, and when they were last assessed. Sources: DOD's internal heartbeat audit (July 2026), party websites, Red Flag, parliamentary records, AEC filings, news media.

### Australian Labor Party
*Scored: August 2026*

- **Left–Right −2 of 10** — Centre-left, social democratic.
- **Internal 3 of 10** — Faction-controlled preselections despite formal OMOV rules; weighted parliamentarian votes in some selections; internal reform pushes from Andrew Leigh and John Faulkner stalled. Sources: [Andrew Leigh on factional duopoly](https://theconversation.com/andrew-leigh-calls-out-how-labors-factional-duopoly-is-undermining-the-party-209972) (The Conversation, 2023); Faulkner's one-member-one-vote push documented in parliamentary and party records.
- **External 4 of 10** — Legislated the National Anti-Corruption Commission Act 2022, but "exceptional circumstances" public-hearings threshold criticised by TI Australia and the Centre for Public Integrity as too restrictive ([joint statement](https://transparency.org.au/joint-statement-on-the-national-anti-corruption-commission-bill-2022/)). 25+ private hearings, zero public as of Dec 2025 ([The New Daily](https://www.thenewdaily.com.au/news/politics/australian-politics/2025/12/18/helen-haines-nacc)).

### Liberal Party / Coalition
*Scored: August 2026*

- **Left–Right +6** — Centre-right, conservative.
- **Internal 2 of 10** — Leader/elite-controlled preselections; branch stacking entrenched in some states.
- **External 0 of 10** — Opposed real-time donation disclosure (federal director called it "too onerous," 2019). Sources: [Canberra Times](https://www.canberratimes.com.au/story/6512005/liberal-party-pushes-back-against-real-time-donations-disclosure/). 2018/19 integrity commission proposal widely criticised as designed to allow only private hearings with no public tip-off pathway ([Crikey](https://www.crikey.com.au/2022/05/17/scott-morrison-promise-federal-icac-with-teeth-haunts-coalition/)).

### Australian Greens
*Scored: August 2026*

- **Left–Right −6** — Left, environmental/social-justice platform.
- **Internal 3 of 10** — Leadership not member-elected in all jurisdictions; preselection processes vary by state; member input on policy platform is stronger than candidate/leadership selection.
- **External 8 of 10** — Strongest external reform record of any Australian parliamentary party. Sources: 10-year federal anti-corruption campaign, won inspector oversight amendments to NACC bill Nov 2022 ([Greens release](https://greens.org.au/news/media-release/nacc-bill-passes-senate-historic-vote-critical-greens-amends-integrity)); truth-in-political-advertising bill modelled on SA law ([Greens ACT](https://greens.org.au/act/news/greens-push-truth-electoral-advertising)); sustained "Clean Up Politics" donations-cap/contractor-donor-ban campaign ([greens.org.au](https://greens.org.au/campaigns/clean-politics)).

### Victorian Socialists
*Scored: August 2026*

- **Left–Right −9** — Far left, revolutionary socialist; abolition of capitalism as stated goal.
- **Internal 7 of 10** — Constitutional commitment to OMOV and party democracy adopted at Jan 2024 conference as part of new constitution. Sources: [VS Our Aims](https://www.victoriansocialists.org.au/about/our-aims). June 2025 members' conference (360 attendees): Communist Caucus ran alternative leadership slate, given platform time, lost at vote — competitive democratic practice. Conference voted to expand democratic structures into electorate-based branches. Sources: [Red Flag](https://redflag.org.au/article/victorian-socialists-conference-resolves-to-expand-party-organisation/).
- **External 0 of 10** — No external governance-reform advocacy. This is deliberate: VS holds that parliament cannot be meaningfully reformed under capitalism, so external advocacy takes the form of building a democratic workers' movement rather than patching existing institutions. The party's aims document describes a democratic socialist vision (recall rights, no special privileges for elected reps, political pluralism) but does not advocate reform of existing parliamentary institutions.

### One Nation
*Scored: August 2026*

- **Left–Right +8** — Right-populist.
- **Internal 1 of 10** — Leader-dominated; party constitution gives Hanson near-total control.
- **External −1** — Cuts against governance reform. AEC compliance action forced withdrawal of $800k+ in contested election-spending claims after ~140 unjustified items, June 2026 ([The Guardian](https://www.theguardian.com/australia-news/2026/jun/29/one-nation-pauline-hanson-election-funding-withdrawals-aec-ntwnfb)).

### Jacqui Lambie Network
*Scored: August 2026*

- **Left–Right +1** — Centre, personality-based.
- **Internal 2 of 10** — Centralised around Lambie; limited evidence of structured member democracy.
- **External 4 of 10** — Sustained criticism of integrity-body design since 2018. Sources: Coalition CIC proposal called "lap dog with dentures" ([Canberra Times](https://www.canberratimes.com.au/story/6998300/lambie-lashes-proposed-corruption-watchdog/)). Donations-disclosure bill on party site; parliamentary progress not independently verified.

### Katter's Australian Party
*Scored: August 2026*

- **Left–Right +7** — Agrarian conservative, populist.
- **Internal 2 of 10** — Leader-dominated; Katter family central to party identity and control.
- **External 1 of 10** — Decentralisation calls and NQ partition referendum — policy positions, not a sustained governance-reform program. Source: [bobkatter.com.au](https://www.bobkatter.com.au/katter-calls-for-decentralisation-of-govt-departments-following-self-absorbing-budget).

### Pirate Party Australia
*Scored: August 2026*

- **Left–Right −3** — Centre-left, digital rights and transparency platform.
- **Internal 6 of 10** — Liquid democracy culture; participatory governance traditions from the international Pirate Party movement. Merged into Fusion Party's federated structure in 2021; continues as distinct internal grouping. Source: [org page](../../organisations/pirate-party-australia.md).
- **External 9 of 10** — Democracy and transparency reform is the party's reason for existing. Initiated the Electoral Royal Commission campaign.

### Australian Democrats
*Scored: August 2026*

- **Left–Right 0 of 10** — Centre, re-established.
- **Internal 3 of 10** — Standard party structures; limited evidence of member governance beyond electoral processes. Notably lower than the *original* party (1977–2010s), which pioneered whole-membership postal-ballot leader elections and binding policy plebiscites in Australia — see the timeline chart (graph 3) for that discontinuity. Source: [Meg Lees](https://en.wikipedia.org/wiki/Meg_Lees).
- **External 7 of 10** — Advocates a randomly selected citizens' assembly for Victoria's upper house electoral reform; proportional representation; evidence-based framing citing 2025 Australian Election Study data (48% support for citizens' assemblies). Source: [org page](../../organisations/australian-democrats.md). See DOD blog post: [Victoria's Upper House inquiry: the case for a citizens' assembly](../../blog/posts/2026-05-24-vic-upper-house-citizens-assembly.md) (May 2026).

### Flux Party
*Scored: August 2026 (based on platform during active period 2016–2022)*

- **Left–Right −2 of 10** — Centre-left, deregistered.
- **Internal 8 of 10** — Issue-Based Direct Democracy: two-token economy (votes + political capital), abstention rewarded as political capital, proportional delegation with revocation. Most sophisticated internal governance design of any Australian party. Sources: [IBDD concept page](../../concepts/issue-based-direct-democracy.md), [org page](../../organisations/flux-party.md).
- **External 9 of 10** — Democracy reform was the entire platform. Deregistered by AEC August 2022; included for historical comparison of governance innovation.

### MiVote
*Scored: August 2026 (based on platform during active period 2014–2019)*

- **Left–Right −1** — Centre, non-partisan framing, deregistered. Political sibling of Flux Party — both launched 2014–2016 with complementary democracy-reform designs.
- **Internal 7 of 10** — Four-destination policy model (not yes/no); structured information pipeline: university research → domain experts → advisory committees (with permanent seats for underrepresented communities) → ethics committee sign-off; 60% supermajority threshold; mandatory mandate binding Senate candidates to aggregated member position. Source: [org page](../../organisations/mivote.md).
- **External 8 of 10** — Democracy reform was the entire platform. Deregistered ~2019 without electing senators. MiVote Technologies continued in the UK.

### Your Party (UK)
*Scored: August 2026*

- **Left–Right −8** — Left, progressive/socialist, international comparator.
- **Internal 9 of 10** — Founding conference delegates selected by sortition via the Sortition Foundation: stratified random sample balanced across gender, region, age, ethnicity, disability, and LGBTQ+ status. One of few parties globally using random selection for internal deliberative bodies. Future conferences to include portion of sortition-selected delegates alongside branch-elected delegates. Source: [org page](../../organisations/your-party.md).
- **External 6 of 10** — Democratic reform in platform (electoral reform, transparency), but also a general-purpose multi-issue party. See [DOD blog post: Your Party is using sortition](https://www.designingopendemocracy.com/blog/2025/12/07/your-party-is-using-sortition/).

## Why this exists

The [Accountability Framework](index.md) is a qualitative standard. It asks *"is this org working on how people participate in governance?"* — a question whose answer is not always yes/no but often *"in what sense, and on which side of its own boundary?"* The framework itself acknowledges this: its "what this means in practice" section does not clarify whether prefigurative internal democracy qualifies, and its diagnostic tools are calibrated for adversary-style accountability systems.

This reference makes the ambiguity quantitative. A party in the top-left of graph 2 (high internal democracy, zero external reform) is answering the framework's question differently than one in the bottom-right (strong external advocacy, factional internals) — and differently again from one in the top-right (both). Whether any of these should qualify for the Democracy Landscape is the open editorial question the heartbeat entry surfaced. This page helps answer it by making the data inspectable rather than buried.

## Expanding the reference

Contributions welcome via PR:
- **Add a party:** Include sourced evidence for each score in the PR description
- **Rescore:** Provide new evidence for changed scores
- **Add international comparators:** Especially parties with novel governance mechanisms (Podemos, M5S, German Pirate Party, Alternativet — see the internal heartbeat research note <!-- ../../internal-heartbeat/2026-07-31-au-parties-democracy-reform-assessment.md --> for method)
- **New graph dimensions:** Membership vs. governance depth, party age vs. mechanism novelty

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
<script>
(function() {
  const DATA_URL = '/data/party-governance.json';

  // Read the page's actual (theme-adaptive) colors rather than hardcoding
  // light-mode values — this site runs a single dark "slate" palette, so a
  // hardcoded dark grey/black would be near-invisible against it.
  const rootStyle = getComputedStyle(document.documentElement);
  const fgText = rootStyle.getPropertyValue('--md-default-fg-color--light').trim() || '#aaa';
  const fgGrid = rootStyle.getPropertyValue('--md-default-fg-color--lightest').trim() || 'rgba(255,255,255,0.1)';

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
    'pirate-party':         { initials: 'PPAU', color: '#9933cc' },
    'australian-democrats': { initials: 'AD',   color: '#daa520' },
    flux:                   { initials: 'FLX',  color: '#00bcd4' },
    mivote:                 { initials: 'MV',   color: '#ff5722' },
    'your-party':           { initials: 'YP',   color: '#e91e8a' }
  };

  function partyGlyph(party) {
    return PARTY_GLYPHS[party.slug] || { initials: party.slug.substring(0,3).toUpperCase(), color: '#999' };
  }

  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1,3), 16), g = parseInt(hex.slice(3,5), 16), b = parseInt(hex.slice(5,7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
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
          ctx.restore();
        });
      }
    };
  }

  let timelineCharts = { internal: null, external: null };

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

  function renderScatter(canvasId, config) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
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
                lines.push('Internal gov: ' + p.internal_governance + '/10');
                lines.push('External reform: ' + p.external_reform + '/10');
                lines.push('Left→Right: ' + p.left_right);
                if (p.notability) lines.push('Notability: ' + p.notability + '/10');
                if (p.note) lines.push(p.note.substring(0, 120) + (p.note.length > 120 ? '...' : ''));
                const latest = p.history && p.history.length
                  ? p.history.reduce((a, b) => (b.date > a.date ? b : a))
                  : null;
                if (latest && latest.source) lines.push('Source: ' + latest.source);
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

    var allLabels = new Set();
    selectedParties.forEach(function(p) {
      p.history.forEach(function(h) { allLabels.add(h.date); });
    });
    var labels = Array.from(allLabels).sort();

    TIMELINE_DIMENSIONS.forEach(function(dim) {
      var datasets = selectedParties.map(function(p) {
        var sorted = p.history.slice().sort(function(a, b) { return a.date.localeCompare(b.date); });
        var g = partyGlyph(p);
        return {
          label: p.name,
          data: sorted.map(function(h) { return { x: h.date, y: h[dim.field], note: h.note, source: h.source }; }),
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
        data: { labels: labels, datasets: datasets },
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
                  if (raw.source) lines.push('Source: ' + raw.source);
                  return lines;
                }
              }
            }
          },
          scales: {
            x: {
              type: 'category',
              title: { display: true, text: 'Date', color: COLORS.text }
            },
            y: {
              min: dim.key === 'external' ? -2 : 0,
              max: 10,
              ticks: { stepSize: 1 },
              title: { display: true, text: dim.yLabel, color: COLORS.text }
            }
          }
        }
      });
    });
  }

  function setupTimeline(parties) {
    var pillsEl = document.getElementById('timeline-pills');
    var DEFAULT_SELECTED = ['victorian-socialists', 'greens', 'your-party'];
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
    .then(data => {
      const parties = data.parties;
      renderTable(parties);

      const graphConfigs = data.graphs;
      renderScatter('chart-left-right-internal', {
        parties: parties,
        x: graphConfigs[0].x_axis,
        y: graphConfigs[0].y_axis,
        xLabel: graphConfigs[0].x_label,
        yLabel: graphConfigs[0].y_label,
        xRange: { min: -10, max: 10 },
        yRange: { min: 0, max: 10 }
      });

      renderScatter('chart-internal-external', {
        parties: parties,
        x: graphConfigs[1].x_axis,
        y: graphConfigs[1].y_axis,
        xLabel: graphConfigs[1].x_label,
        yLabel: graphConfigs[1].y_label,
        xRange: { min: 0, max: 10 },
        yRange: { min: -2, max: 10 }
      });

      setupTimeline(parties);
    })
    .catch(err => {
      console.error('Failed to load party governance data:', err);
      const charts = document.querySelectorAll('.chart-container');
      charts.forEach(c => c.innerHTML = '<p style="color:#c00">Failed to load chart data.</p>');
    });
})();
</script>
