# Fursee — Fursuit Identity Retrieval

> Hybrid YOLO-DINOv3 Framework for Fursuit Identity Retrieval and Clustering

**Paper**: arXiv:2606.22872  
**Author**: Jundi Wu, Shandong University

**GUI Shell**: [ant-cave](https://github.com/ant-cave) · antmmmmm@outlook.com

A three-stage computer vision pipeline for detecting, recognizing, and clustering fursuit characters:

```
Stage 1 [Detection]   → YOLO crops "furry" targets from images
Stage 2 [Embedding]   → DINOv3 converts crops into 512-dim feature vectors
Stage 3 [Search/Cluster] → Custom .fvdb vector database + DBSCAN clustering
```

---

## 🖥️ GUI Shell

This repo includes a web-based graphical interface built with **FastAPI + Vue 3 (Naive UI)** — no CLI knowledge required.

### Quick Start

```bash
bash start.sh
```

Open **http://localhost:8898** in your browser.

### Features

| Page | Description |
|---|---|
| **Easy Mode** (傻瓜模式) | Upload images → auto detect → extract → classify → download ZIP. Fully self-contained. |
| **Dashboard** | Dataset overview, stats, quick actions |
| **Image Manager** | Upload/delete images in 3 categories |
| **Database Build** | Cold build or incremental append |
| **Clustering** | DBSCAN parameter tuning |
| **Similarity Search** | Top-K search with reference image |
| **Identity Retrieval** | Identify character groups from reference images |

### Architecture

```
fursee_api/          ← FastAPI backend (7 files)
├── main.py          Entry, CORS, WebSocket, SPA serving
├── core/
│   ├── task_manager.py   Async task queue
│   └── worker.py         tqdm hook + pipeline execution
└── api/
    ├── images.py     Image CRUD
    ├── pipeline.py   Pipeline endpoints
    └── results.py    Result browsing + ZIP download

fursee_ui/           ← Vue 3 + Naive UI frontend (12 files)
├── src/
│   ├── App.vue      Sidebar nav, responsive, i18n
│   ├── router/      6 + 1 routes
│   ├── composables/ useApi (axios) + useWs (WebSocket)
│   ├── i18n/        zh.json + en.json
│   └── views/       7 pages
├── vite.config.ts   Proxy /api → :8000
└── package.json     vue3, naive-ui, axios, vue-i18n
```

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, uvicorn, websockets |
| Frontend | Vue 3, TypeScript, Naive UI, Vite |
| ML Engine | YOLOv8 (ultralytics), DINOv3 (HuggingFace), scikit-learn |
| Database | Custom .fvdb binary vector format |

### API Endpoints (14 total)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Dataset statistics |
| GET/POST/DELETE | `/api/images/{category}/...` | Image management |
| POST | `/api/pipeline/{db,classify,similar,identify,auto}` | Pipeline tasks |
| GET | `/api/pipeline/tasks` | Task list & status |
| GET | `/api/results/{classify,similar,identify,auto}/...` | Results & ZIP |
| WS | `/api/ws/{task_id}` | Real-time progress |

---

## 📚 Citation

```bibtex
@misc{wu2026fursee,
  author = {Jundi Wu},
  title = {Fursee: Hybrid YOLO-DINOv3 Framework for Fursuit Identity Retrieval and Clustering},
  year = {2026},
  eprint = {2606.22872},
  archivePrefix = {arXiv},
}
```

## 📄 License

Core Fursee pipeline (by Jundi Wu): see [LICENSE.md](LICENSE.md).  
GUI Shell (by ant-cave): AGPL-3.0 — see [LICENSE.md](LICENSE.md) for combined terms.
