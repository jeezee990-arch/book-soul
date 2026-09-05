import { HashRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import Inspiration from "./pages/Inspiration";
import Creation from "./pages/Creation";
import QualityCheck from "./pages/QualityCheck";
import Library from "./pages/Library";
import Settings from "./pages/Settings";
import Skills from "./pages/Skills";

/**
 * Phase 2 模块 2.1：路由与基础布局
 * 5 个页面占位 + 顶栏 + 侧栏
 */
export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Inspiration />} />
            <Route path="/creation" element={<Creation />} />
            <Route path="/quality" element={<QualityCheck />} />
            <Route path="/library" element={<Library />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  );
}
