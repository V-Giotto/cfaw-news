import { Component, type ReactNode } from 'react'

export default class BriefingBoundary extends Component<{ children: ReactNode; openLibrary: () => void }, { failed: boolean; generation: number }> {
  state = { failed: false, generation: 0 }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (this.state.failed) return <section className="briefing-empty" role="alert"><h1>情报页面暂时无法显示</h1>
      <p>可以重试读取，或继续使用原始资讯库。</p>
      <div className="briefing-actions"><button className="button secondary" onClick={this.props.openLibrary}>打开原始资讯库</button>
        <button className="button primary" onClick={() => this.setState(s => ({ failed: false, generation: s.generation + 1 }))}>重试情报页面</button></div></section>
    return <div key={this.state.generation}>{this.props.children}</div>
  }
}
