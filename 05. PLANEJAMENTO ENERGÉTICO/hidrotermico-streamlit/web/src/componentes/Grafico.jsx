import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, TreeChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, TreeChart, HeatmapChart, VisualMapComponent, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer])

// Envolve um gráfico ECharts: recebe `opcao` (objeto de configuração) e redesenha quando ela muda.
export default function Grafico({ opcao, altura = 300 }) {
  const ref = useRef(null)
  const grafico = useRef(null)
  useEffect(() => {
    grafico.current = echarts.init(ref.current)
    const ajustar = () => grafico.current && grafico.current.resize()
    window.addEventListener('resize', ajustar)
    const obs = new ResizeObserver(ajustar); obs.observe(ref.current)
    return () => { window.removeEventListener('resize', ajustar); obs.disconnect(); grafico.current.dispose(); grafico.current = null }
  }, [])
  useEffect(() => { grafico.current && grafico.current.setOption(opcao, true) }, [opcao])
  return <div ref={ref} style={{ width: '100%', height: altura }} />
}
