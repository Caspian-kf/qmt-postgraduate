const DATA_FILES = {
  materials: "kaoyan_materials.json",
  scores: "score_lines.json",
  admissions: "admission_stats.json",
  exams: "exam_info.json"
};

const DATA_PREFIXES = ["../data/", "data/", "/data/"];

let store = {
  materials: [],
  scores: [],
  admissions: [],
  exams: [],
  errors: {}
};

document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  store = await loadAllData();

  const page = document.body.dataset.page;
  if (page === "home") renderHome();
  if (page === "data") renderDataPage();
  if (page === "score") renderScorePage();
  if (page === "admission") renderAdmissionPage();
  if (page === "analysis") renderAnalysisPage();
});

function setupNavigation() {
  const toggle = document.querySelector("[data-nav-toggle]");
  const links = document.querySelector("[data-nav-links]");
  if (!toggle || !links) return;
  toggle.addEventListener("click", () => links.classList.toggle("open"));
}

async function loadAllData() {
  const result = { materials: [], scores: [], admissions: [], exams: [], errors: {} };
  for (const [key, filename] of Object.entries(DATA_FILES)) {
    const loaded = await loadJson(filename);
    result[key] = loaded.data;
    if (loaded.error) result.errors[key] = loaded.error;
  }
  return result;
}

async function loadJson(filename) {
  for (const prefix of DATA_PREFIXES) {
    try {
      const response = await fetch(`${prefix}${filename}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      return { data: Array.isArray(data) ? data : [], error: "" };
    } catch (error) {
      console.warn(`读取数据失败：${prefix}${filename}`, error);
    }
  }
  return { data: [], error: `${filename} 暂无数据或读取失败` };
}

function renderHome() {
  const status = document.getElementById("home-status");
  const cards = document.getElementById("dashboard-cards");
  const overview = document.getElementById("core-overview");
  if (!cards) return;

  const years = uniqueValues([
    ...store.materials.map(itemYear),
    ...store.scores.map((item) => item.year),
    ...store.admissions.map((item) => item.year),
    ...store.exams.map((item) => item.year)
  ].filter(Boolean));

  const latest = latestCrawlTime();
  const cardData = [
    ["信息总数", store.materials.length],
    ["已采集年份数", years.length],
    ["分数线记录数", store.scores.length],
    ["录取统计记录数", store.admissions.length],
    ["考试信息记录数", store.exams.length],
    ["最近采集时间", latest || "暂无数据"]
  ];

  cards.innerHTML = cardData.map(([label, value]) => statCard(label, value)).join("");

  if (overview) {
    const materialScore = latestScoreByMajor("材料科学与工程");
    const electronicScore = latestScoreByMajor("电子信息");
    const latestAdmission = latestAdmissionCount();
    overview.innerHTML = [
      coreCard("最新年份材料科学与工程复试分数线", formatScore(materialScore)),
      coreCard("最新年份电子信息复试分数线", formatScore(electronicScore)),
      coreCard("最新年份拟录取人数", latestAdmission || "暂无结构化数据"),
      coreCard("最新更新时间", latest || "暂无数据")
    ].join("");
  }

  if (status) {
    status.textContent = `已读取 ${store.materials.length} 条原始信息、${store.scores.length} 条分数线、${store.admissions.length} 条录取统计`;
  }
}

function renderDataPage() {
  const status = document.getElementById("data-status");
  const category = document.getElementById("category-filter");
  const source = document.getElementById("source-filter");
  const year = document.getElementById("year-filter");
  const keyword = document.getElementById("keyword-search");
  const reset = document.getElementById("reset-filters");

  fillSelect(category, uniqueValues(store.materials.map((item) => item.category)));
  fillSelect(source, uniqueValues(store.materials.map((item) => item.source)));
  fillSelect(year, uniqueValues(store.materials.map(itemYear)).sort((a, b) => b.localeCompare(a)));

  const apply = () => {
    const filtered = store.materials.filter((item) => {
      const haystack = Object.values(item).join(" ").toLowerCase();
      return (!category.value || item.category === category.value)
        && (!source.value || item.source === source.value)
        && (!year.value || itemYear(item) === year.value)
        && (!keyword.value || haystack.includes(keyword.value.trim().toLowerCase()));
    });
    renderMaterialTable(filtered);
  };

  [category, source, year, keyword].forEach((control) => control && control.addEventListener("input", apply));
  if (reset) {
    reset.addEventListener("click", () => {
      [category, source, year, keyword].forEach((control) => {
        if (control) control.value = "";
      });
      apply();
    });
  }

  if (status) status.textContent = store.errors.materials || "数据读取完成";
  renderMaterialTable(store.materials);
}

function renderMaterialTable(data) {
  const tbody = document.getElementById("data-table-body");
  const count = document.getElementById("table-count");
  const empty = document.getElementById("empty-message");
  if (!tbody) return;
  tbody.innerHTML = data.map((item) => `
    <tr>
      <td><span class="tag">${show(item.category)}</span></td>
      <td class="title-cell">${show(item.title)}</td>
      <td class="summary-cell">${show(item.content)}</td>
      <td>${show(item.publish_time)}</td>
      <td>${show(item.source)}</td>
      <td class="link-cell">${renderLink(item.url)}</td>
      <td>${show(item.crawl_time)}</td>
    </tr>
  `).join("");
  if (count) count.textContent = `${data.length} 条信息`;
  if (empty) empty.classList.toggle("hidden", data.length > 0);
}

function renderScorePage() {
  const year = document.getElementById("score-year-filter");
  const major = document.getElementById("score-major-filter");
  const sort = document.getElementById("score-sort");
  const status = document.getElementById("score-status");
  let descending = true;

  fillSelect(year, uniqueValues(store.scores.map((item) => item.year)).sort((a, b) => b.localeCompare(a)));
  fillSelect(major, uniqueValues(store.scores.map((item) => item.major_name)));

  const apply = () => {
    let data = store.scores.filter((item) => {
      return (!year.value || item.year === year.value)
        && (!major.value || item.major_name === major.value);
    });
    data = data.sort((a, b) => {
      const diff = Number(b.score_line || 0) - Number(a.score_line || 0);
      return descending ? diff : -diff;
    });
    renderScoreTable(data);
  };

  [year, major].forEach((control) => control && control.addEventListener("input", apply));
  if (sort) {
    sort.addEventListener("click", () => {
      descending = !descending;
      sort.textContent = descending ? "按分数降序" : "按分数升序";
      apply();
    });
  }
  if (status) status.textContent = store.errors.scores || "数据读取完成";
  renderScoreTable(store.scores);
}

function renderScoreTable(data) {
  const tbody = document.getElementById("score-table-body");
  const count = document.getElementById("score-count");
  const empty = document.getElementById("score-empty-message");
  if (!tbody) return;
  tbody.innerHTML = data.map((item) => `
    <tr>
      <td>${show(item.year)}</td>
      <td>${show(item.college)}</td>
      <td>${show(item.major_code)}</td>
      <td>${show(item.major_name)}</td>
      <td>${show(item.degree_type)}</td>
      <td>${show(item.study_type)}</td>
      <td><strong>${show(item.score_line)}</strong></td>
      <td class="link-cell">${renderLink(item.source_url)}</td>
    </tr>
  `).join("");
  if (count) count.textContent = `${data.length} 条分数线`;
  if (empty) empty.classList.toggle("hidden", data.length > 0);
}

function renderAdmissionPage() {
  const status = document.getElementById("admission-status");
  if (status) status.textContent = store.errors.admissions || "数据读取完成";
  renderAdmissionTable(store.admissions);
}

function renderAdmissionTable(data) {
  const tbody = document.getElementById("admission-table-body");
  const count = document.getElementById("admission-count");
  const empty = document.getElementById("admission-empty-message");
  if (!tbody) return;
  tbody.innerHTML = data.map((item) => `
    <tr>
      <td>${show(item.year)}</td>
      <td>${show(item.major_code)}</td>
      <td>${show(item.major_name)}</td>
      <td>${show(item.planned_enrollment)}</td>
      <td>${show(item.reexam_count)}</td>
      <td>${show(item.admitted_count)}</td>
      <td>${show(item.adjustment_count)}</td>
      <td>${show(item.lowest_score)}</td>
      <td>${show(item.highest_score)}</td>
      <td>${show(item.average_score)}</td>
      <td class="link-cell">${renderLink(item.source_url)}</td>
      <td class="summary-cell">${show(item.note)}</td>
    </tr>
  `).join("");
  if (count) count.textContent = `${data.length} 条录取统计`;
  if (empty) empty.classList.toggle("hidden", data.length > 0);
}

function renderAnalysisPage() {
  const status = document.getElementById("analysis-status");
  if (!window.echarts) {
    if (status) status.textContent = "ECharts 加载失败，请检查网络或 CDN。";
    return;
  }

  if (status) {
    status.textContent = `已读取 ${store.scores.length} 条分数线、${store.admissions.length} 条录取统计、${store.materials.length} 条原始信息`;
  }

  renderLineChart("score-trend-chart", buildScoreTrend());
  renderBarChart("score-major-chart", "复试线", latestScoreByMajorMap(), "#1668dc");
  renderBarChart("admission-count-chart", "录取人数", admissionByYear(), "#16866f");
  renderBarChart("category-chart", "类别数量", countBy(store.materials, "category"), "#b45f06");
  renderBarChart("source-chart", "来源数量", countBy(store.materials, "source"), "#7a3db8");

  window.addEventListener("resize", () => {
    document.querySelectorAll(".chart").forEach((node) => {
      const chart = echarts.getInstanceByDom(node);
      if (chart) chart.resize();
    });
  });
}

function renderLineChart(elementId, seriesData) {
  const element = document.getElementById(elementId);
  if (!element) return;
  if (!seriesData.years.length) return renderEmptyChart(element);
  const chart = echarts.init(element);
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 48, right: 24, top: 42, bottom: 52 },
    xAxis: { type: "category", data: seriesData.years },
    yAxis: { type: "value", minInterval: 1 },
    series: seriesData.series.map((item) => ({
      name: item.name,
      type: "line",
      smooth: true,
      connectNulls: true,
      data: item.values
    }))
  });
}

function renderBarChart(elementId, name, counts, color) {
  const element = document.getElementById(elementId);
  if (!element) return;
  const entries = Object.entries(counts).filter(([, value]) => value !== "" && value !== null && value !== undefined);
  if (!entries.length) return renderEmptyChart(element);
  const chart = echarts.init(element);
  chart.setOption({
    color: [color],
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 20, top: 28, bottom: 72 },
    xAxis: { type: "category", data: entries.map(([key]) => key || "未知"), axisLabel: { interval: 0, rotate: entries.length > 4 ? 28 : 0 } },
    yAxis: { type: "value", minInterval: 1 },
    series: [{ name, type: "bar", data: entries.map(([, value]) => Number(value) || 0), barMaxWidth: 42 }]
  });
}

function renderEmptyChart(element) {
  element.innerHTML = '<p class="empty-message">暂无数据，无法生成图表。</p>';
}

function buildScoreTrend() {
  const years = uniqueValues(store.scores.map((item) => item.year).filter(Boolean)).sort();
  const majors = uniqueValues(store.scores.map((item) => item.major_name).filter(Boolean));
  const series = majors.map((major) => ({
    name: major,
    values: years.map((year) => {
      const item = store.scores.find((row) => row.year === year && row.major_name === major && row.score_line);
      return item ? Number(item.score_line) : null;
    })
  }));
  return { years, series };
}

function latestScoreByMajorMap() {
  const map = {};
  uniqueValues(store.scores.map((item) => item.major_name)).forEach((major) => {
    const item = latestScoreByMajor(major);
    if (item && item.score_line) map[major] = item.score_line;
  });
  return map;
}

function admissionByYear() {
  return store.admissions.reduce((acc, item) => {
    if (!item.year || !item.admitted_count) return acc;
    acc[item.year] = (acc[item.year] || 0) + Number(item.admitted_count || 0);
    return acc;
  }, {});
}

function latestScoreByMajor(majorName) {
  return store.scores
    .filter((item) => item.major_name && item.major_name.includes(majorName) && item.score_line)
    .sort((a, b) => String(b.year).localeCompare(String(a.year)) || Number(b.score_line) - Number(a.score_line))[0];
}

function latestAdmissionCount() {
  const item = store.admissions
    .filter((row) => row.admitted_count)
    .sort((a, b) => String(b.year).localeCompare(String(a.year)))[0];
  return item ? `${item.year || "-"} 年 ${item.major_name || ""}：${item.admitted_count} 人` : "";
}

function latestCrawlTime() {
  return [
    ...store.materials.map((item) => item.crawl_time),
    ...store.scores.map((item) => item.crawl_time),
    ...store.admissions.map((item) => item.crawl_time),
    ...store.exams.map((item) => item.crawl_time)
  ].filter(Boolean).sort().at(-1);
}

function formatScore(item) {
  if (!item) return "暂无结构化数据";
  return `${item.year || "-"} 年：${item.score_line || "-"} 分`;
}

function statCard(label, value) {
  return `<article class="stat-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value || "-"))}</strong></article>`;
}

function coreCard(label, value) {
  return `<article class="info-card compact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value || "-"))}</strong></article>`;
}

function fillSelect(select, values) {
  if (!select) return;
  const first = select.querySelector("option") ? select.querySelector("option").cloneNode(true) : null;
  select.innerHTML = "";
  if (first) select.appendChild(first);
  values.filter(Boolean).forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function countBy(data, field) {
  return data.reduce((acc, item) => {
    const key = item[field] || "未知";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "zh-CN"));
}

function itemYear(item) {
  return String(item.publish_time || item.crawl_time || "").match(/\d{4}/)?.[0] || "";
}

function renderLink(url) {
  if (!url) return "-";
  const firstUrl = String(url).split("；")[0];
  return `<a href="${escapeHtml(firstUrl)}" target="_blank" rel="noopener">查看来源</a>`;
}

function show(value) {
  const text = String(value || "").trim();
  return text ? escapeHtml(text) : "-";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
