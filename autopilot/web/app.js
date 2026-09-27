/**
 * AI News Video Creator — Interactive Cyber Dashboard Client
 */

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initTabNavigation();
  initTopics();
  initScriptEditor();
  initPipelineAndGenerator();
  initHealthCheckDock();
  initMediaPreviewTabs();
  initHistoryAndAnalytics();
  initSettings();
});

/* ==========================================================================
   1. Sidebar & Layout Micro-Interactions
   ========================================================================== */
function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const collapseBtn = document.getElementById('collapseBtn');

  if (collapseBtn && sidebar) {
    collapseBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      const isCollapsed = sidebar.classList.contains('collapsed');
      collapseBtn.querySelector('svg').style.transform = isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)';
    });
  }
}

/* ==========================================================================
   2. Page Navigation & Tab Switching
   ========================================================================== */
function initTabNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  const pageViews = document.querySelectorAll('.page-view');

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetTab = item.getAttribute('data-tab');
      
      navItems.forEach(nav => nav.classList.remove('active'));
      item.classList.add('active');

      pageViews.forEach(view => {
        if (view.id === `${targetTab}Page`) {
          view.classList.remove('hidden');
        } else {
          view.classList.add('hidden');
        }
      });
    });
  });
}

/* ==========================================================================
   3. Topic Selection & News Feed (5 Items matching Image 2)
   ========================================================================== */
const sampleTopics = [
  {
    id: 1,
    source: 'TechCrunch',
    sourceIcon: 'TC',
    iconClass: 'tc',
    title: 'OpenAI announces major AI improvements',
    time: '2 hours ago',
    script: `OpenAI has officially unveiled GPT-5, the latest version of its flagship AI model, bringing significant improvements in reasoning, creativity, and multimodal capabilities. The new model is expected to deliver better performance across coding, healthcare, and education, making it more useful for both individuals and businesses.\n\nOpenAI says GPT-5 will be available to ChatGPT users in the coming weeks, with a focus on safety and reliability...`,
    wordCount: 342,
    duration: '1m 42s'
  },
  {
    id: 2,
    source: 'The Verge',
    sourceIcon: 'V',
    iconClass: 'tv',
    title: 'Apple announces new AI features in iOS 18',
    time: '3 hours ago',
    script: `Apple today announced Apple Intelligence, a suite of new AI capabilities integrated into iOS 18, iPadOS 18, and macOS Sequoia. The new features focus on writing assistance, image generation, and personalized Siri capabilities powered by privacy-focused on-device models.\n\nDevelopers will gain access to these new APIs starting next month in developer beta releases.`,
    wordCount: 280,
    duration: '1m 24s'
  },
  {
    id: 3,
    source: 'Reuters',
    sourceIcon: 'RT',
    iconClass: 'rt',
    title: 'Google launches Gemini 1.5 Pro with larger context window',
    time: '4 hours ago',
    script: `Google Cloud has released Gemini 1.5 Pro with an unprecedented 2 million token context window. This capability allows developers to process hours of video, audio, or hundreds of thousands of lines of code in a single prompt.\n\nEnterprise benchmarks demonstrate massive efficiency gains for automated code translation and document analysis.`,
    wordCount: 310,
    duration: '1m 35s'
  },
  {
    id: 4,
    source: 'Reeborn',
    sourceIcon: 'B',
    iconClass: 'mashable',
    title: 'Meta rolls out new AI tools for creators',
    time: '5 hours ago',
    script: `Meta has unveiled its latest suite of generative AI tools for video content creators and advertisers. The tools enable automatic video background generation, voice dubbing across 20 languages, and smart caption overlays.\n\nCreator beta tests show a 40% reduction in edit turnarounds.`,
    wordCount: 265,
    duration: '1m 18s'
  },
  {
    id: 5,
    source: 'ZDNet',
    sourceIcon: 'ZD',
    iconClass: 'zdnet',
    title: 'Microsoft introduces Copilot+ PCs with AI features',
    time: '6 hours ago',
    script: `Microsoft introduced Copilot+ PCs, a new category of Windows 11 devices equipped with NPUs capable of over 40 TOPS. Key features include Recall timeline search, live captions with real-time translation, and on-device image generation.`,
    wordCount: 290,
    duration: '1m 30s'
  }
];

let selectedTopic = sampleTopics[0];

function initTopics() {
  const sourcePills = document.querySelectorAll('.pill-btn');
  const fetchBtn = document.getElementById('fetchTopicBtn');
  const customTopicInput = document.getElementById('customTopicInput');

  renderNewsList(sampleTopics);

  sourcePills.forEach(pill => {
    pill.addEventListener('click', () => {
      sourcePills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });

  if (fetchBtn) {
    fetchBtn.addEventListener('click', () => {
      const query = customTopicInput.value.trim();
      if (!query) {
        showToast('Please enter a topic or URL first!', 'warning');
        return;
      }
      
      showToast(`Fetching latest news for: "${query}"...`, 'info');
      fetchBtn.disabled = true;
      fetchBtn.innerHTML = 'Fetching...';

      setTimeout(() => {
        fetchBtn.disabled = false;
        fetchBtn.innerHTML = 'Fetch';
        const newTopic = {
          id: Date.now(),
          source: 'Custom Source',
          sourceIcon: 'CS',
          iconClass: 'tc',
          title: `Latest Updates on: ${query}`,
          time: 'Just now',
          script: `Here is the AI generated news summary for "${query}". Recent developments highlight groundbreaking progress in automation, performance benchmarks, and real-world adoption.`,
          wordCount: 295,
          duration: '1m 28s'
        };
        sampleTopics.unshift(newTopic);
        renderNewsList(sampleTopics);
        selectTopicItem(newTopic);
        showToast('New topic fetched successfully!', 'success');
      }, 1000);
    });
  }
}

function renderNewsList(topics) {
  const newsList = document.getElementById('newsList');
  if (!newsList) return;

  newsList.innerHTML = topics.map(t => `
    <div class="news-item ${t.id === selectedTopic.id ? 'selected' : ''}" data-id="${t.id}">
      <div class="news-item-left">
        <div class="news-source-icon ${t.iconClass}">${t.sourceIcon}</div>
        <div class="news-item-info">
          <h4>${t.title}</h4>
          <span>${t.source} • ${t.time}</span>
        </div>
      </div>
      <div class="checkbox-circle"></div>
    </div>
  `).join('');

  document.querySelectorAll('.news-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = parseInt(el.getAttribute('data-id'));
      const found = sampleTopics.find(x => x.id === id);
      if (found) selectTopicItem(found);
    });
  });
}

function selectTopicItem(topic) {
  selectedTopic = topic;
  
  document.querySelectorAll('.news-item').forEach(el => {
    if (parseInt(el.getAttribute('data-id')) === topic.id) {
      el.classList.add('selected');
    } else {
      el.classList.remove('selected');
    }
  });

  const headlineEl = document.getElementById('scriptHeadline');
  const wordCountBadge = document.getElementById('wordCountBadge');
  const durationBadge = document.getElementById('durationBadge');

  if (headlineEl) headlineEl.textContent = topic.title;
  if (wordCountBadge) wordCountBadge.textContent = `📄 Word Count: ${topic.wordCount}`;
  if (durationBadge) durationBadge.textContent = `⏱ Est. Duration: ${topic.duration}`;
  
  typewriterScript(topic.script);
}

/* ==========================================================================
   4. Script Editor & Typewriter Animation
   ========================================================================== */
function initScriptEditor() {
  const regenBtn = document.getElementById('regenScriptBtn');
  const approveBtn = document.getElementById('approveScriptBtn');

  if (regenBtn) {
    regenBtn.addEventListener('click', () => {
      triggerAiWritingAnimation();
    });
  }

  if (approveBtn) {
    approveBtn.addEventListener('click', () => {
      showToast('Script approved and saved for video generation!', 'success');
    });
  }
}

function triggerAiWritingAnimation() {
  const aiIndicator = document.getElementById('aiWritingIndicator');
  const textarea = document.getElementById('scriptTextarea');

  if (aiIndicator) aiIndicator.classList.remove('hidden');
  if (textarea) textarea.value = '';

  setTimeout(() => {
    if (aiIndicator) aiIndicator.classList.add('hidden');
    typewriterScript(selectedTopic.script);
    showToast('New AI script generated!', 'success');
  }, 1200);
}

function typewriterScript(text) {
  const textarea = document.getElementById('scriptTextarea');
  if (!textarea) return;

  textarea.value = '';
  let i = 0;
  const speed = 6;

  function type() {
    if (i < text.length) {
      textarea.value += text.charAt(i);
      i++;
      setTimeout(type, speed);
    }
  }
  type();
}

/* ==========================================================================
   5. Generate Video & Pipeline Animation
   ========================================================================== */
function initPipelineAndGenerator() {
  const generateBtn = document.getElementById('generateVideoBtn');

  if (generateBtn) {
    generateBtn.addEventListener('click', () => {
      startPipelineExecution();
    });
  }
}

function startPipelineExecution() {
  const generateBtn = document.getElementById('generateVideoBtn');
  const equalizerBox = document.getElementById('equalizerBox');
  const progressFill = document.getElementById('pipelineProgressFill');
  const percentText = document.getElementById('pipelinePercentText');
  const chip = document.getElementById('pipelineStatusChip');

  generateBtn.disabled = true;
  generateBtn.querySelector('.btn-text').textContent = 'Generating Video...';
  
  if (chip) {
    chip.innerHTML = '<span class="pulse-dot-green">●</span> Running';
    chip.className = 'status-chip running';
  }

  showToast('Video generation started successfully!', 'success');

  // Reset steps
  updatePipelineStepState(1, 'active');
  for (let i = 2; i <= 5; i++) updatePipelineStepState(i, 'pending');

  setTimeout(() => {
    updatePipelineStepState(1, 'completed', '(2s)');
    updatePipelineStepState(2, 'active');
    updateProgress(20);
  }, 1000);

  setTimeout(() => {
    updatePipelineStepState(2, 'completed', '(8s)');
    updatePipelineStepState(3, 'active');
    updateProgress(40);
  }, 2200);

  setTimeout(() => {
    updatePipelineStepState(3, 'completed', '(12s)');
    updatePipelineStepState(4, 'active');
    if (equalizerBox) equalizerBox.classList.remove('hidden');
    updateProgress(65);
  }, 4000);

  setTimeout(() => {
    updatePipelineStepState(4, 'completed', '(24s)');
    if (equalizerBox) equalizerBox.classList.add('hidden');
    updatePipelineStepState(5, 'active');
    updateProgress(85);
  }, 6000);

  setTimeout(() => {
    updatePipelineStepState(5, 'completed', '(5s)');
    updateProgress(100);

    if (chip) {
      chip.innerHTML = '<span class="pulse-dot-green">●</span> Completed';
      chip.className = 'status-chip running';
    }

    generateBtn.disabled = false;
    generateBtn.querySelector('.btn-text').textContent = 'Generate Video';

    showToast('🎉 Video created & published successfully!', 'success');
  }, 7800);

  function updateProgress(val) {
    if (progressFill) progressFill.style.width = `${val}%`;
    if (percentText) percentText.textContent = `${val}%`;
  }
}

function updatePipelineStepState(stepNum, state, timeText = '') {
  const stepEl = document.querySelector(`.step-item[data-step="${stepNum}"]`);
  if (!stepEl) return;

  stepEl.className = `step-item ${state}`;
  const badge = stepEl.querySelector('.step-badge');
  const timeSpan = stepEl.querySelector('.step-time');

  if (state === 'completed') {
    stepEl.querySelector('.step-icon').innerHTML = '<span class="check-svg">✓</span>';
    if (badge) {
      badge.className = 'step-badge completed';
      badge.innerHTML = '<span class="check-icon">✓</span> Completed';
    }
    if (timeSpan && timeText) timeSpan.textContent = timeText;
  } else if (state === 'active') {
    stepEl.querySelector('.step-icon').innerHTML = '🎙️';
    if (badge) {
      badge.className = 'step-badge active';
      badge.textContent = 'In Progress...';
    }
  } else {
    stepEl.querySelector('.step-icon').innerHTML = '<span class="circle-outline">⭕</span>';
    if (badge) {
      badge.className = 'step-badge pending';
      badge.textContent = 'Pending';
    }
  }
}

/* ==========================================================================
   6. System Health Diagnostic Dock & Overlay matching Image 2
   ========================================================================== */
function initHealthCheckDock() {
  const checkHealthBtn = document.getElementById('checkHealthBtn');
  const healthDock = document.getElementById('systemHealthDock');
  const closeHealthDock = document.getElementById('closeHealthDock');
  const reRunDiagnosticsBtn = document.getElementById('reRunDiagnosticsBtn');

  if (checkHealthBtn && healthDock) {
    checkHealthBtn.addEventListener('click', () => {
      healthDock.classList.toggle('hidden');
    });
  }

  if (closeHealthDock && healthDock) {
    closeHealthDock.addEventListener('click', () => {
      healthDock.classList.add('hidden');
    });
  }

  if (reRunDiagnosticsBtn) {
    reRunDiagnosticsBtn.addEventListener('click', () => {
      runDiagnosticCheckAnimation();
    });
  }
}

function runDiagnosticCheckAnimation() {
  const statuses = document.querySelectorAll('.health-checks-grid .h-status');
  statuses.forEach(st => {
    st.className = 'h-status warning';
    st.textContent = 'Checking... 🔵';
  });

  statuses.forEach((st, idx) => {
    setTimeout(() => {
      st.className = 'h-status healthy';
      st.textContent = 'Connected ✓';
    }, (idx + 1) * 250);
  });

  setTimeout(() => {
    showToast('All system diagnostic checks completed (7/7 Healthy ✓)', 'success');
  }, 2000);
}

/* ==========================================================================
   7. Media Preview Tabs & Controls
   ========================================================================== */
function initMediaPreviewTabs() {
  const tabBtns = document.querySelectorAll('.media-tabs .tab-btn');
  const mediaContents = document.querySelectorAll('.media-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.getAttribute('data-media');

      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      mediaContents.forEach(c => {
        if (c.id === `${type}MediaContent`) {
          c.classList.remove('hidden');
          c.classList.add('active');
        } else {
          c.classList.add('hidden');
          c.classList.remove('active');
        }
      });
    });
  });

  const downloadSrtBtn = document.getElementById('downloadSrtBtn');
  const downloadThumbBtn = document.getElementById('downloadThumbBtn');

  if (downloadSrtBtn) {
    downloadSrtBtn.addEventListener('click', () => {
      showToast('Downloading subtitles (.srt) file...', 'info');
    });
  }

  if (downloadThumbBtn) {
    downloadThumbBtn.addEventListener('click', () => {
      showToast('Downloading thumbnail (.jpg) file...', 'info');
    });
  }
}

/* ==========================================================================
   8. History Search & Table Filtering
   ========================================================================== */
function initHistoryAndAnalytics() {
  const historySearch = document.getElementById('historySearch');
  if (historySearch) {
    historySearch.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      const rows = document.querySelectorAll('#historyTableBody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }
}

/* ==========================================================================
   9. Settings Form
   ========================================================================== */
function initSettings() {
  const saveBtn = document.getElementById('saveSettingsBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      showToast('Settings & API credentials saved successfully!', 'success');
    });
  }
}

/* ==========================================================================
   10. Toast Notification Helper
   ========================================================================== */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✓';
  if (type === 'warning') icon = '⚠️';
  if (type === 'error') icon = '❌';

  toast.innerHTML = `
    <span class="toast-check">${icon}</span>
    <span>${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
