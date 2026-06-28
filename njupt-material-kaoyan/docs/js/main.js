const DATA_PATHS = [
  "../data/kaoyan_materials.json",
  "/data/kaoyan_materials.json",
  "data/kaoyan_materials.json"
];

const REQUIRED_CATEGORIES = [
  "招生简章",
  "专业目录",
  "考试大纲",
  "复试细则",
  "拟录取名单",
  "调剂信息"
];

let cachedData = [];

document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();

  const page = document.body.dataset.page;
  const result = await loadKaoyanData();
  cachedData = result.data;

  if (page === "home") {
    renderHome(cachedData, result.error);
  }

  if (page === "data") {
    renderDataPage(cachedData, result.error);
  }

  if (page === "analysis") {
    renderAnalysisPage(cachedData, result.error);
  }
});

function setupNavigation() {
  const toggle = document.querySelector("[data-nav-toggle]");
  const links = document.querySelector("[data-nav-links]");

  if (!toggle || !links) return;

  toggle.addEventListener("click", () => {
    links.classList.toggle("open");
  });
}

async function loadKaoyanData() {
  for (const path of DATA_PATHS) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      return { data: Array.isArray(data) ? data : [], error: "" };
    } catch (error) {
      console.warn(`读取数据失败：${path}`, error);
    }
  }

  return {
    data: [],
    error: "未能读取 data/kaoyan_materials.json。请确认数据文件存在，或通过本地静态服务器访问页面。"
  };
}

function renderHome(data, error) {
  const status = document.getElementById("home-status");
  const container = document.getElementById("dashboard-cards");
  if (!container) return;

  const categoryCounts = countBy(data, "category");
  const cards = [
    { label: "总信息数量", value: data.length },
    ...REQUIRED_CATEGORIES.map((category) => ({
      label: `${category}数量`,
      value: categoryCounts[category] || 0
    })),
    { label: "最近采集时间", value: getLatestCrawlTime(data) || "暂无数据", className: "recent" }
  ];

  container.innerHTML = cards
    .map((card) => `
      <article class="stat-card ${card.className || ""}">
        <span>${escapeHtml(card.label)}</span>
        <strong>${escapeHtml(String(card.value))}</strong>
      </article>
    `)
    .join("");

  if (status) {
    status.textContent = error || `已读取 ${data.length} 条公开信息`;
  }
}

function renderDataPage(data, error) {
  const status = document.getElementById("data-status");
  const categoryFilter = document.getElementById("category-filter");
  const sourceFilter = document.getElementById("source-filter");
  const keywordSearch = document.getElementById("keyword-search");
  const resetButton = document.getElementById("reset-filters");

  if (status) {
    status.textContent = error || "数据读取完成";
  }

  fillSelect(categoryFilter, uniqueValues(data, "category"));
  fillSelect(sourceFilter, uniqueValues(data, "source"));

  const applyFilters = () => {
    const filtered = filterData(data, {
      category: categoryFilter ? categoryFilter.value : "",
      source: sourceFilter ? sourceFilter.value : "",
      keyword: keywordSearch ? keywordSearch.value : ""
    });
    renderTable(filtered);
  };

  [categoryFilter, sourceFilter, keywordSearch].forEach((control) => {
    if (control) control.addEventListener("input", applyFilters);
  });

  if (resetButton) {
    resetButton.addEventListener("click", () => {
      if (categoryFilter) categoryFilter.value = "";
      if (sourceFilter) sourceFilter.value = "";
      if (keywordSearch) keywordSearch.value = "";
      applyFilters();
    });
  }

  renderTable(data);
}

function fillSelect(select, values) {
  if (!select) return;
  const currentFirst = select.querySelector("option");
  select.innerHTML = "";
  if (currentFirst) select.appendChild(currentFirst);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function filterData(data, filters) {
  const keyword = filters.keyword.trim().toLowerCase();

  return data.filter((item) => {
    const matchCategory = !filters.category || item.category === filters.category;
    const matchSource = !filters.source || item.source === filters.source;
    const haystack = [
      item.school,
      item.college,
      item.major,
      item.category,
      item.title,
      item.content,
      item.publish_time,
      item.source,
      item.url
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const matchKeyword = !keyword || haystack.includes(keyword);
    return matchCategory && matchSource && matchKeyword;
  });
}

function renderTable(data) {
  const tbody = document.getElementById("data-table-body");
  const count = document.getElementById("table-count");
  const empty = document.getElementById("empty-message");
  if (!tbody) return;

  tbody.innerHTML = data
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.school || "")}</td>
        <td>${escapeHtml(item.college || "")}</td>
        <td>${escapeHtml(item.major || "")}</td>
        <td><span class="tag">${escapeHtml(item.category || "其他")}</span></td>
        <td class="title-cell">${escapeHtml(item.title || "")}</td>
        <td class="summary-cell">${escapeHtml(item.content || "")}</td>
        <td>${escapeHtml(item.publish_time || "")}</td>
        <td>${escapeHtml(item.source || "")}</td>
        <td class="link-cell">${renderLink(item.url)}</td>
        <td>${escapeHtml(item.crawl_time || "")}</td>
      </tr>
    `)
    .join("");

  if (count) count.textContent = `${data.length} 条信息`;
  if (empty) empty.classList.toggle("hidden", data.length > 0);
}

function renderLink(url) {
  if (!url) return "暂无链接";
  const safeUrl = escapeHtml(url);
  return `<a href="${safeUrl}" target="_blank" rel="noopener">查看原文</a>`;
}

function renderAnalysisPage(data, error) {
  const status = document.getElementById("analysis-status");

  if (status) {
    status.textContent = error || `已生成 ${data.length} 条信息的统计图表`;
  }

  if (!window.echarts) {
    if (status) status.textContent = "ECharts 加载失败，请检查网络或 CDN。";
    return;
  }

  if (!data.length) {
    renderEmptyCharts();
    return;
  }

  renderBarChart("category-chart", "类别", countBy(data, "category"), "#1668dc");
  renderBarChart("source-chart", "来源", countBy(data, "source"), "#16866f");
  renderBarChart("year-chart", "年份", countByYear(data), "#b45f06");

  window.addEventListener("resize", () => {
    document.querySelectorAll(".chart").forEach((chart) => {
      const instance = echarts.getInstanceByDom(chart);
      if (instance) instance.resize();
    });
  });
}

function renderBarChart(elementId, name, counts, color) {
  const element = document.getElementById(elementId);
  if (!element) return;

  const entries = Object.entries(counts).sort((a, b) => String(a[0]).localeCompare(String(b[0]), "zh-CN"));
  const chart = echarts.init(element);
  chart.setOption({
    color: [color],
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 20, top: 28, bottom: 72 },
    xAxis: {
      type: "category",
      data: entries.map(([key]) => key || "未知"),
      axisLabel: { interval: 0, rotate: entries.length > 4 ? 28 : 0 }
    },
    yAxis: {
      type: "value",
      minInterval: 1
    },
    series: [
      {
        name,
        type: "bar",
        data: entries.map(([, value]) => value),
        barMaxWidth: 42
      }
    ]
  });
}

function renderEmptyCharts() {
  ["category-chart", "source-chart", "year-chart"].forEach((id) => {
    const element = document.getElementById(id);
    if (element) {
      element.innerHTML = '<p class="empty-message">暂无数据，无法生成图表。</p>';
    }
  });
}

function countBy(data, field) {
  return data.reduce((acc, item) => {
    const key = item[field] || "未知";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function countByYear(data) {
  return data.reduce((acc, item) => {
    const value = item.publish_time || item.crawl_time || "";
    const match = String(value).match(/\d{4}/);
    const year = match ? match[0] : "未知";
    acc[year] = (acc[year] || 0) + 1;
    return acc;
  }, {});
}

function uniqueValues(data, field) {
  return [...new Set(data.map((item) => item[field]).filter(Boolean))]
    .sort((a, b) => String(a).localeCompare(String(b), "zh-CN"));
}

function getLatestCrawlTime(data) {
  return data
    .map((item) => item.crawl_time)
    .filter(Boolean)
    .sort()
    .at(-1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
