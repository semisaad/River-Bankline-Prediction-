import { useEffect, useRef, useState } from 'react'
import {
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  config,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './App.css'

config.WORKER_URL = '/maplibre-gl-worker.mjs'

const CENTER = [89.75, 24.45]
const YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]

const BASEMAP = {
  version: 8,
  sources: {
    esri: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Imagery © Esri',
    },
  },
  layers: [{ id: 'esri', type: 'raster', source: 'esri' }],
}

function emptyFC() {
  return { type: 'FeatureCollection', features: [] }
}

export default function App() {
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const [year, setYear] = useState(2023)
  const [playing, setPlaying] = useState(false)
  const [summary, setSummary] = useState(null)
  const [future, setFuture] = useState(null)
  const [showFuture, setShowFuture] = useState(false)
  const [risk, setRisk] = useState(null)
  const [showRisk, setShowRisk] = useState(false)

  useEffect(() => {
    fetch('/api/predictions/')
      .then((r) => (r.ok ? r.json() : null))
      .then((fc) => {
        if (!fc || !fc.features || !fc.features.length) return
        const trends = fc.features.filter(
          (f) => f.properties?.kind === 'long_run_trend',
        )
        if (!trends.length) return
        const rates = trends.map((f) =>
          Math.abs(f.properties?.rate_m_per_yr || 0),
        )
        setFuture({
          horizon: trends[0].properties?.horizon_years,
          baseYear: fc.metadata?.base_year,
          n: trends.length,
          nSignificant: fc.metadata?.n_significant ?? 0,
          max: Math.max(0, ...rates),
        })
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/api/risk/summary/')
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        if (s) setRisk(s)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const map = new MapLibreMap({
      container: mapContainer.current,
      style: BASEMAP,
      center: CENTER,
      zoom: 9.2,
    })
    map.addControl(new NavigationControl(), 'top-right')
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right')

    map.on('load', () => {
      map.addSource('bankline', { type: 'geojson', data: emptyFC() })
      map.addLayer({
        id: 'bankline',
        type: 'line',
        source: 'bankline',
        paint: {
          'line-color': '#00e5ff',
          'line-width': 3,
          'line-opacity': 0.95,
        },
      })

      map.addSource('erosion', { type: 'geojson', data: emptyFC() })
      map.addLayer({
        id: 'erosion',
        type: 'line',
        source: 'erosion',
        paint: {
          'line-width': 4,
          'line-opacity': 0.95,
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'rate_m_yr'],
            -200, '#2f80ed',
            -50, '#56ccf2',
            0, '#cccccc',
            50, '#ffd166',
            200, '#ef5350',
          ],
        },
      })

      map.addSource('risk', { type: 'geojson', data: emptyFC() })
      map.addLayer({
        id: 'risk',
        type: 'line',
        source: 'risk',
        layout: { 'line-cap': 'butt' },
        paint: {
          'line-width': [
            'interpolate',
            ['linear'],
            ['get', 'rate_median'],
            -80, 2,
            0, 3,
            80, 12,
          ],
          'line-opacity': [
            'case',
            ['==', ['get', 'significant'], true],
            0.95,
            0.4,
          ],
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'rate_median'],
            -60, '#2f80ed',
            -10, '#56ccf2',
            0, '#c9d6e3',
            15, '#ffd166',
            40, '#ff8f3d',
            80, '#ef5350',
          ],
        },
      })

      map.addSource('predicted', { type: 'geojson', data: emptyFC() })
      map.addLayer({
        id: 'predicted',
        type: 'line',
        source: 'predicted',
        paint: {
          'line-width': 5,
          'line-opacity': 0.95,
          'line-dasharray': [2, 1.5],
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'rate_m_per_yr'],
            -100, '#2f80ed',
            0, '#c9d6e3',
            100, '#ff8f3d',
            250, '#ff2e2e',
          ],
        },
      })
    })

    map.on('error', (e) => console.warn('map error', e?.error?.message))
    mapRef.current = map
    return () => map.remove()
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const apply = () => {
      fetch(`/api/banklines/?year=${year}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((fc) => {
          if (fc) map.getSource('bankline')?.setData(fc)
        })
        .catch(() => {})

      if (year <= YEARS[0]) {
        map.getSource('erosion')?.setData(emptyFC())
        setSummary(null)
        return
      }
      const pair = `${year - 1}_${year}`
      fetch(`/api/erosion/?pair=${pair}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((fc) => {
          if (!fc) {
            map.getSource('erosion')?.setData(emptyFC())
            setSummary(null)
            return
          }
          map.getSource('erosion')?.setData(fc)
          const rates = fc.features.map((f) => Math.abs(f.properties.rate_m_yr || 0))
          rates.sort((a, b) => a - b)
          const med = rates.length ? rates[Math.floor(rates.length / 2)] : 0
          const mx = rates.length ? rates[rates.length - 1] : 0
          const net = fc.features.reduce(
            (s, f) => s + Math.max(0, f.properties.rate_m_yr || 0),
            0,
          )
          setSummary({
            pair,
            median: med.toFixed(0),
            max: mx.toFixed(0),
            eroding: fc.features.filter((f) => (f.properties.rate_m_yr || 0) > 5).length,
            total: fc.features.length,
          })
        })
        .catch(() => {})
        .catch(() => {})
    }

    if (map.isStyleLoaded() && map.getSource('bankline')) apply()
    else map.once('load', apply)
  }, [year])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !future) return

    const draw = () => {
      if (!showFuture) {
        map.getSource('predicted')?.setData(emptyFC())
        return
      }
      fetch('/api/predictions/')
        .then((r) => (r.ok ? r.json() : null))
        .then((fc) => {
          if (!fc || !fc.features) {
            map.getSource('predicted')?.setData(emptyFC())
            return
          }
          // The file carries both the measured bankline it was built from and
          // the projected one. Drawing the measured line in "forecast" style
          // would misrepresent where the projection actually is.
          const trends = fc.features.filter(
            (f) => f.properties?.kind === 'long_run_trend',
          )
          map
            .getSource('predicted')
            ?.setData({ ...fc, features: trends })
        })
        .catch(() => {})
    }

    if (map.isStyleLoaded() && map.getSource('predicted')) draw()
    else map.once('load', draw)
  }, [future, showFuture])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const draw = () => {
      if (!showRisk) {
        map.getSource('risk')?.setData(emptyFC())
        return
      }
      fetch('/api/risk/?min_years=10')
        .then((r) => (r.ok ? r.json() : null))
        .then((fc) => {
          if (fc && fc.features) map.getSource('risk')?.setData(fc)
          else map.getSource('risk')?.setData(emptyFC())
        })
        .catch(() => {})
    }

    if (map.isStyleLoaded() && map.getSource('risk')) draw()
    else map.once('load', draw)
  }, [showRisk])

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      setYear((y) => {
        const i = YEARS.indexOf(y)
        return YEARS[(i + 1) % YEARS.length]
      })
    }, 1100)
    return () => clearInterval(id)
  }, [playing])

  return (
    <div className="app">
      <div ref={mapContainer} className="map" />

      <div className="card title-card">
        <h1>RiverGuard</h1>
        <p>Jamuna River · bankline migration</p>
      </div>

      <div className="card legend">
        <div className="legend-title">Bank change (m/yr)</div>
        <div><span className="swatch eros" /> land gained</div>
        <div><span className="swatch stable" /> no change</div>
        <div><span className="swatch mid" /> slow</div>
        <div><span className="swatch hot" /> fast</div>
        <div><span className="swatch bank" /> bankline</div>
      </div>

      {(showRisk || showFuture) && (
        <div className="card note-card">
          <strong>Not a forecast.</strong> Year-to-year erosion was tested and
          found unpredictable — nothing beat simply predicting the average.
          {showFuture && future && (
            <>
              {' '}These dashed lines are the{' '}
              <strong>{future.horizon}-year long-run trend</strong> from{' '}
              {future.baseYear}, based on {future.n} measured bank positions,
              only {future.nSignificant} of which are statistically
              distinguishable from zero.
            </>
          )}
          {showRisk && risk && (
            <>
              {' '}Thick lines are chronic erosion risk over the full record;
              faded ones could not be distinguished from no change (
              {risk.records_significant}/{risk.records_eligible}).
            </>
          )}
        </div>
      )}

      {showRisk && risk && (
        <div className="card stats-card">
          <div className="stat-head">Chronic risk · {risk.records_eligible} records</div>
          <div>very high {risk.tiers['very high'] || 0} · high{' '}
            {risk.tiers['high'] || 0} · moderate {risk.tiers['moderate'] || 0}</div>
          <div>{risk.records_insufficient} records too short to rank</div>
        </div>
      )}

      {summary && (
        <div className="card stats-card">
          <div className="stat-head">{summary.pair.replace('_', ' → ')}</div>
          <div>median {summary.median} m/yr · max {summary.max} m/yr</div>
          <div>{summary.eroding}/{summary.total} transects eroding</div>
        </div>
      )}

      <div className="card controls">
        {risk && (
          <button
            className={`future-btn ${showRisk ? 'on' : ''}`}
            onClick={() => setShowRisk((s) => !s)}
          >
            {showRisk ? 'Hide' : 'Show'} chronic risk
          </button>
        )}
        {future && (
          <button
            className={`future-btn ${showFuture ? 'on' : ''}`}
            onClick={() => setShowFuture((s) => !s)}
          >
            {showFuture ? 'Hide' : 'Show'} {future.horizon}-yr trend
          </button>
        )}
        <button className="play" onClick={() => setPlaying((p) => !p)}>
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          min={0}
          max={YEARS.length - 1}
          value={YEARS.indexOf(year)}
          onChange={(e) => {
            setPlaying(false)
            setYear(YEARS[Number(e.target.value)])
          }}
        />
        <span className="year">{year}</span>
      </div>
    </div>
  )
}