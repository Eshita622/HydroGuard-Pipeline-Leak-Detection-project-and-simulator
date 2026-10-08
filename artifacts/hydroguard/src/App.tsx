import { useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './simulator-flow.css';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, Check, CheckCircle2,
  ChevronDown, ClipboardList, Download, Droplets, Gauge, LayoutDashboard, LogOut, Map as MapIcon,
  Menu, Radio, Search, Settings as SettingsIcon, ShieldCheck, Smartphone, Users, Wrench, X,
  UserRound, FileBarChart2, Waves, Clock3, Plus, Pencil, Save, Send, Signal,
  Zap, CalendarDays, Filter, LockKeyhole, Mail, Phone, MapPin, Leaf, Sparkles, BatteryCharging,
  TrendingDown, Globe, Sun, ArrowLeft,
} from 'lucide-react';
import {
  useHealthCheck, useGetAuthSession, useLogoutUser, useRegisterUser, useLoginUser,
  useGetDashboard, useGetSensors, useGetPipelines, useSubmitSensorReading,
  useGetAlerts, useAcknowledgeAlert, useAssignAlert, useResolveAlert, useStartAlertMaintenance,
  useGetMaintenance, useCreateMaintenance, useUpdateMaintenance, useGetWaterChampions,
  useGetAnalytics, useGetReport, useGetProfile, useUpdateProfile, useGetSmsLog,
  useGetSettings, useUpdateSettings, setAuthTokenGetter, getHealthCheckQueryKey, getGetAuthSessionQueryKey, getGetDashboardQueryKey,
  getGetSensorsQueryKey, getGetPipelinesQueryKey, getGetAlertsQueryKey, getGetMaintenanceQueryKey,
  getGetWaterChampionsQueryKey, getGetAnalyticsQueryKey,
  getGetProfileQueryKey, getGetSettingsQueryKey, getGetReportQueryKey, getGetSmsLogQueryKey, setBaseUrl,
} from '@workspace/api-client-react';
import { apiUrl, API_BASE_URL } from './lib/runtime-config';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { LanguageProvider, useLanguage, LanguageToggle } from './lib/i18n';

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } } });
setBaseUrl(API_BASE_URL || null);
setAuthTokenGetter(() => typeof localStorage === 'undefined' ? null : localStorage.getItem('hg_access_token'));
const items = [
  { to: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { to: '/sustainability', label: 'Sustainability', icon: Leaf },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/map', label: 'Pipeline map', icon: MapIcon },
  { to: '/analytics', label: 'Analytics', icon: Activity },
  { to: '/maintenance', label: 'Maintenance', icon: Wrench },
  { to: '/champions', label: 'Water Champions', icon: Users },
  { to: '/reports', label: 'Reports', icon: FileBarChart2 },
];
const adminItems = [
  { to: '/simulation', label: 'Sensor simulation', icon: Radio },
  { to: '/settings', label: 'System settings', icon: SettingsIcon },
];
const cn = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(' ');
const human = (value?: string) => value ? value.replaceAll('-', ' ').replaceAll('_', ' ') : '—';
const dateTime = (value?: string) => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
const shortTime = (value?: string) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
function getSimulatorId() {
  const key = 'hg_simulator_id';
  try {
    let id = localStorage.getItem(key);
    if (!id) {
      id = window.crypto?.randomUUID?.() || `sim-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return `sim-${Date.now()}`;
  }
}
const errorText = (error: unknown) => {
  if (!error) return 'The service could not complete this request.';
  const e = error as { message?: string; status?: number };
  return e.message || 'The service could not complete this request.';
};

function Button({ children, variant = 'primary', className = '', ...props }: any) {
  return <button className={cn('btn', `btn-${variant}`, className)} {...props}>{children}</button>;
}
function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t } = useLanguage();
  return <div className="error-box"><AlertTriangle size={18}/><div><b>{t('couldNotLoadView')}</b><p>{errorText(error)}</p>{retry && <button onClick={retry} className="text-action">{t('tryAgain')}</button>}</div></div>;
}
function isNetworkFailure(error: unknown) {
  const status = (error as { status?: number } | null)?.status;
  return !status || status >= 500;
}
function ServerUnavailable({ retry }: { retry: () => void }) {
  return <main className="not-found" role="alert">
    <div className="brand-mark"><Waves size={22}/></div>
    <span className="eyebrow">HYDROGUARD CONNECTION</span>
    <h1 className="font-display">Can&apos;t reach server</h1>
    <p>Check your internet connection and try again.</p>
    <button className="btn btn-primary" onClick={retry}>Try again <ArrowRight size={16}/></button>
  </main>;
}
function Skeleton({ rows = 3 }: { rows?: number }) {
  return <div className="skeleton-stack" aria-label="Loading">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton skeleton-row" />)}</div>;
}
function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span className="empty-mark"><Droplets size={21}/></span><b>{title}</b><p>{detail}</p></div>;
}
function PageTitle({ kicker, title, detail, action }: any) {
  return <div className="page-title"><div><div className="eyebrow">{kicker}</div><h1 className="font-display">{title}</h1>{detail && <p>{detail}</p>}</div>{action}</div>;
}
function Status({ value }: { value?: string }) {
  const { t } = useLanguage();
  if (!value) return <span className="status status-neutral"><i/>—</span>;
  const v = value.toLowerCase().trim();
  const kind = ['critical', 'leak', 'failed', 'high risk'].includes(v) ? 'critical' : ['warning', 'high', 'medium', 'medium risk', 'assigned', 'in-progress', 'in_progress', 'on-site', 'on_site'].includes(v) ? 'warning' : ['resolved', 'completed', 'available', 'operational', 'online', 'sent', 'demo-sent', 'low', 'low risk', 'normal', 'normal risk'].includes(v) ? 'good' : 'neutral';
  const key = 'status_' + v.replace(/[- ]/g, '_');
  const label = t(key, human(value));
  return <span className={`status status-${kind}`}><i/>{label}</span>;
}
function Metric({ label, value, suffix, icon: Icon, note, trend, critical }: any) {
  return <article className={cn('metric-card panel', critical && 'metric-critical')}><div className="metric-top"><span>{label}</span><Icon size={17}/></div><div className="metric-value font-data">{value ?? '—'}<small>{suffix}</small></div><div className="metric-foot">{trend && <span className="metric-trend">{trend > 0 ? <ArrowUpRight size={14}/> : <ArrowDownRight size={14}/>} {Math.abs(trend)}%</span>}<span>{note}</span></div></article>;
}
function SectionHead({ title, aside }: any) { return <div className="section-head"><h2 className="font-display">{title}</h2>{aside}</div>; }

function AppFrame({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { t } = useLanguage();
  const session = useGetAuthSession();
  const serviceHealth = useHealthCheck({ query: { queryKey: getHealthCheckQueryKey(), refetchInterval: 60000 } });
  const logout = useLogoutUser();
  const navigate = useNavigate();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const getNavLabel = (to: string, defaultLabel: string) => {
    switch (to) {
      case '/dashboard': return t('navOverview');
      case '/sustainability': return t('navSustainability');
      case '/alerts': return t('navAlerts');
      case '/map': return t('navMap');
      case '/analytics': return t('navAnalytics');
      case '/maintenance': return t('navMaintenance');
      case '/champions': return t('navChampions');
      case '/reports': return t('navReports');
      case '/simulation': return t('navSimulation');
      case '/settings': return t('navSettings');
      default: return defaultLabel;
    }
  };

  if (session.isLoading) return <div className="screen-loading"><div className="brand-mark"><Waves size={24}/></div><div className="skeleton" style={{ width: 180, height: 12 }}/></div>;
  if (session.isError && isNetworkFailure(session.error)) return <ServerUnavailable retry={() => session.refetch()}/>;
  if (session.isError || !session.data?.user) return <Navigate to="/login" replace state={{ from: loc.pathname }}/>;
  const user = session.data.user;
  const isAdmin = user.role === 'administrator';
  if (adminOnly && !isAdmin) return <Navigate to="/dashboard" replace/>;
  const navItems = isAdmin ? [...items, ...adminItems] : items.filter(({ to }) => !['/reports'].includes(to));
  const doLogout = () => logout.mutate(undefined, { onSuccess: () => { localStorage.removeItem('hg_access_token'); queryClient.clear(); navigate('/login'); } });
  return <div className="app-shell">
    <aside className={cn('sidebar', mobileOpen && 'sidebar-open')}>
      <div className="brand"><div className="brand-mark"><Waves size={21}/></div><div><b>Hydro<span>Guard</span></b><small>{t('brandSubtitle')}</small></div><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18}/></button></div>
      <div className="side-label">{t('operations')}</div>
      <nav className="side-nav">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            onClick={() => setMobileOpen(false)}
            key={to}
            to={to}
            className={({ isActive }) => cn('nav-link', isActive && 'active')}
          >
            <Icon size={17} />
            <span>{getNavLabel(to, label)}</span>
            {to === '/alerts' && <AlertCount />}
          </NavLink>
        ))}
      </nav>
      <div className="side-spacer"/>
      <div className="network-card"><div className="network-icon"><Signal size={16}/></div><div><b>{t('serviceStatus')}</b><small><i/>{serviceHealth.isLoading?t('checkingService'):serviceHealth.isError?t('serviceUnavailable'):serviceHealth.data?.status||t('connected')}</small></div></div>
      <NavLink to="/profile" className="profile-mini"><span className="avatar">{user.fullName.split(' ').map((x: string) => x[0]).slice(0,2).join('').toUpperCase()}</span><span className="profile-mini-copy"><b>{user.fullName}</b><small>{isAdmin ? t('administrator') : t('waterChampion')}</small></span><ChevronDown size={15}/></NavLink>
      <button className="logout-link" onClick={doLogout} disabled={logout.isPending}><LogOut size={16}/>{logout.isPending ? t('signingOut') : t('signOut')}</button>
    </aside>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)}/>}
    <main className="main-panel">
      <header className="topbar">
        <button className="mobile-menu" aria-label="Open menu" onClick={() => setMobileOpen(true)}><Menu size={20}/></button>
        <div className="breadcrumb">HydroGuard <span>/</span> <b>{getNavLabel(loc.pathname, items.concat(adminItems).find(i => i.to === loc.pathname)?.label || (loc.pathname === '/profile' ? t('navProfile') : t('operations')))}</b></div>
        <div className="top-right">
          <LanguageToggle />
          <span className="top-divider"/>
          <span className="live-pill"><i/>{serviceHealth.isLoading?'CONNECTING':serviceHealth.isError?'SERVICE UNAVAILABLE':String(serviceHealth.data?.status||'CONNECTED').toUpperCase()}</span>
          <span className="top-divider"/>
          <span className="top-user">{user.assignedZone || t('networkWide')}</span>
        </div>
      </header>
      <div className="page-content">{children}</div>
    </main>
    <nav className="bottom-nav">{[...items.slice(0,4),{ to:'/profile',label:t('navProfile'),icon:UserRound }].map(({ to,label,icon:Icon }) => <NavLink key={to} to={to} className={({isActive})=>cn('bottom-link',isActive&&'active')}><Icon size={18}/><span>{getNavLabel(to, label)}</span></NavLink>)}</nav>
  </div>;
}
function AlertCount() {
  const q = useGetAlerts({ query: { queryKey: getGetAlertsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const n = Array.isArray(q.data) ? q.data.filter(a => a.status !== 'resolved').length : 0;
  return n > 0 ? <em className="nav-count">{n}</em> : null;
}

function AlertNotifications({ enabled }: { enabled: boolean }) {
  const { t } = useLanguage();
  const q = useGetAlerts({ query: {
    queryKey: getGetAlertsQueryKey(),
    enabled,
    refetchInterval: enabled ? 2000 : false,
    refetchIntervalInBackground: true,
  } });
  const navigate = useNavigate();
  const previous = useRef<Map<string, number> | null>(null);
  const sequence = useRef(0);
  const [notices, setNotices] = useState<any[]>([]);

  useEffect(() => {
    if (!enabled) {
      previous.current = null;
      setNotices([]);
      return;
    }
    if (!Array.isArray(q.data)) return;
    const active = q.data.filter(alert => alert.status !== 'resolved');
    const current = new Map(active.map(alert => [
      alert.id,
      ({ low: 1, medium: 2, high: 3 } as Record<string, number>)[alert.riskLevel || ''] || 0,
    ]));
    if (previous.current === null) {
      previous.current = current;
      return;
    }
    for (const alert of active) {
      const risk = ({ low: 1, medium: 2, high: 3 } as Record<string, number>)[alert.riskLevel || ''] || 0;
      const oldRisk = previous.current.get(alert.id);
      if (oldRisk !== undefined && risk <= oldRisk) continue;
      const notice = { ...alert, noticeId: ++sequence.current };
      setNotices(old => [...old, notice].slice(-4));
      window.setTimeout(() => {
        setNotices(old => old.filter(item => item.noticeId !== notice.noticeId));
      }, 8000);
    }
    previous.current = current;
  }, [enabled, q.data]);

  if (!notices.length) return null;
  return <div className="alert-toast-stack" aria-live="polite" aria-label="New alert notifications">
    {notices.map(alert => {
      const riskFormatted = alert.riskLevel ? alert.riskLevel.charAt(0).toUpperCase() + alert.riskLevel.slice(1) : 'High';
      const riskHeading = alert.riskTitle || `${t('status_'+(alert.riskLevel||'high'), riskFormatted)} · ${alert.type}`;
      const zoneHeading = alert.zone || t('networkWide', 'Network');
      return <button className={`alert-toast toast-${alert.riskLevel || 'new'}`} key={alert.noticeId}
        onClick={() => { setNotices(old => old.filter(item => item.noticeId !== alert.noticeId)); navigate(`/alerts?alertId=${encodeURIComponent(alert.id)}`); }}>
        <span className="toast-icon"><Bell size={17}/></span>
        <span className="toast-copy">
          <b>{riskHeading}</b>
          <small>{zoneHeading} · {alert.location}</small>
          <small>{alert.simulated ? t('simulatedAlertModal', 'SIMULATED ALERT') : t('fieldAlertModal', 'FIELD ALERT')} · {dateTime(alert.createdAt)}</small>
          {alert.riskLevel === 'high' && alert.mockSmsMessage && <small className="toast-sms">{alert.mockSmsMessage}</small>}
        </span><X size={15}/>
      </button>;
    })}
  </div>;
}

function AuthPage({ register = false }: { register?: boolean }) {
  const { t } = useLanguage();
  const nav = useNavigate();
  const location = useLocation();
  const login = useLoginUser(); const signup = useRegisterUser();
  const [formError, setFormError] = useState('');
  const [account, setAccount] = useState({ fullName:'', email:'', mobile:'', password:'', role:'administrator' });
  const busy = login.isPending || signup.isPending;
  const done = (result: any) => {
    if (result?.access_token) localStorage.setItem('hg_access_token', result.access_token);
    const target = (location.state as any)?.from;
    const userRole = result?.user?.role || signup.data?.user?.role || login.data?.user?.role;
    queryClient.invalidateQueries({ queryKey:getGetAuthSessionQueryKey() });
    nav(target || (userRole === 'water-champion' ? '/dashboard' : '/dashboard'), { replace:true });
  };
  const submitAccount = (e: React.FormEvent) => {
    e.preventDefault(); setFormError('');
    if (register) {
      signup.mutate({ data: { fullName:account.fullName, email:account.email, mobile:account.mobile, password:account.password, role:account.role as any } }, { onSuccess:done, onError:e=>setFormError(errorText(e)) });
    } else {
      login.mutate({ data:{ identifier:account.email, password:account.password } }, { onSuccess:done, onError:e=>setFormError(errorText(e)) });
    }
  };
  return <div className="auth-screen"><div className="auth-left"><div className="auth-brand"><div className="brand-mark"><Waves size={24}/></div><b>Hydro<span>Guard</span></b><small>{t('brandSubtitle')}</small></div><div className="auth-hero"><span className="eyebrow">{t('authHeroEyebrow', 'WATER, WATCHED WELL')}</span><h1 className="font-display">{t('authHeroTitle')}<br/><i>{t('authHeroTitleItalic')}</i></h1><p>{t('authHeroSubtitle')}</p><div className="auth-diagram"><div className="water-flow"><span/><span/><span/><span/><span/><span/></div><div className="diagram-main"><div className="diag-tag"><i/> {t('diagDistributionLine', 'DISTRIBUTION LINE')}</div><div className="pipe-line"><span className="pipe-node"/><span className="pipe-node"/><span className="pipe-node"/><span className="pipe-node"/></div><div className="diagram-labels"><span>{t('diagIntake', 'INTAKE')}</span><span>{t('diagPressure', 'PRESSURE')}</span><span>{t('diagDistribution', 'DISTRIBUTION')}</span><span>{t('diagStorage', 'STORAGE')}</span></div><div className="diagram-readout"><div><small>{t('diagDataLink', 'DATA LINK')}</small><b>{t('diagBackend', 'BACKEND')} <small>{t('diagManaged', 'MANAGED')}</small></b></div><div><small>{t('diagSensorSignal', 'SENSOR SIGNAL')}</small><b><i/> {t('diagTelemetry', 'TELEMETRY')}</b></div></div></div></div></div><div className="auth-foot"><span>{t('authTagline')}</span><span>{t('authCopyright', '© HYDROGUARD OPERATIONS')}</span></div></div>
  <div className="auth-right"><div className="auth-card">
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
      <div className="eyebrow" style={{ margin: 0 }}>{register ? t('createYourAccount') : t('secureAccess')}</div>
      <LanguageToggle />
    </div>
    <h2 className="font-display">{register ? t('joinNetwork') : t('welcomeBack')}</h2><p className="auth-intro">{register ? t('registerIntro') : t('signInIntro')}</p>
    <form onSubmit={submitAccount} className="form-stack">{register && <label>{t('fullName')}<input value={account.fullName} onChange={e=>setAccount({...account,fullName:e.target.value})} minLength={2} maxLength={120} required placeholder={t('fullNamePlaceholder')}/></label>}
      {register && <label>{t('mobileNumber')}<input value={account.mobile} onChange={e=>setAccount({...account,mobile:e.target.value})} required minLength={8} maxLength={24} placeholder="+1 555 010 2468"/></label>}
      <label>{register ? t('workEmail') : t('emailOrMobile')}<div className="input-icon"><Mail size={16}/><input value={account.email} onChange={e=>setAccount({...account,email:e.target.value})} required placeholder={register?'name@utility.gov':t('emailPlaceholder')} type={register?'email':'text'}/></div></label>
      <label>{t('password')}<div className="input-icon"><LockKeyhole size={16}/><input type="password" minLength={register?8:1} required value={account.password} onChange={e=>setAccount({...account,password:e.target.value})} placeholder={register?'At least 8 characters':t('passwordPlaceholder')}/></div></label>
      {register && <label>{t('accountRole')}<select value={account.role} onChange={e=>setAccount({...account,role:e.target.value})}><option value="administrator">{t('administrator')}</option><option value="water-champion">{t('waterChampion')}</option></select></label>}
      {formError && <div className="inline-error">{formError}</div>}{(login.isError || signup.isError) && !formError && <div className="inline-error">{errorText(login.error || signup.error)}</div>}
       <Button disabled={busy}>{busy?t('pleaseWait'):register?t('createAccount'):t('signIn')} <ArrowRight size={17}/></Button></form>
    <div className="auth-switch">{register?t('alreadyHaveAccess'):t('newToHydroguard')} <NavLink to={register?'/login':'/register'}>{register?t('signIn'):t('createAnAccount')}</NavLink></div>
    <div className="auth-security"><ShieldCheck size={16}/><span>{t('protectedByAuth')}</span></div>
  </div></div></div>;
}

function Dashboard() {
  const { t } = useLanguage();
  const q = useGetDashboard({ query: { queryKey: getGetDashboardQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const health = useHealthCheck({ query: { queryKey: getHealthCheckQueryKey(), refetchInterval: 60000 } });
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('hg_access_token') : null;
  const simLoss = useQuery({
    queryKey: ['simulated-water-loss'],
    queryFn: async () => {
      const res = await fetch(apiUrl('/api/simulation/water-loss'), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
  const data = q.data;
  return <><PageTitle kicker={t('overviewKicker')} title={t('goodMorning')} detail={t('overviewDetail')} action={<div className="last-updated"><span className="live-pulse"/><span>{t('lastSync')}</span><b>{dateTime(data?.updatedAt)}</b></div>}/>
  {q.isLoading ? <><div className="metric-grid">{[1,2,3,4].map(i=><div key={i} className="panel metric-card"><div className="skeleton" style={{height:12,width:'50%'}}/><div className="skeleton" style={{height:32,width:'40%',marginTop:22}}/><div className="skeleton" style={{height:10,width:'72%',marginTop:20}}/></div>)}</div><div className="panel skeleton" style={{height:260,marginTop:18}}/></> : q.isError ? <ErrorBox error={q.error} retry={()=>q.refetch()}/> : !data ? <Empty title={t('couldNotLoadView')} detail={t('noActiveAlertsDetail')}/> : <>
    <div className="overview-banner"><div className="banner-signal"><ShieldCheck size={20}/></div><div><span className="eyebrow">{t('systemCondition')}</span><h2><Status value={data.systemStatus}/> <i/> <small>{t('liveNetworkState')}</small></h2></div><div className="banner-right"><span>{t('serviceConnection')}</span><b className={health.data?.status==='ok'?'healthy-text':''}>{health.data?.status ? t('connected') : t('checkingService')}</b></div></div>
     <div className="metric-grid"><Metric label={t('pipelineNetwork')} value={data.metrics.pipelineLengthKm} suffix="km" icon={Waves} note={`${data.metrics.activeFlowMeters} ${t('activeFlowMeters')}`}/><Metric label={t('sensorsOnline')} value={`${data.metrics.onlineSensors}/${data.metrics.totalSensors}`} icon={Radio} note={t('fieldTelemetry')}/><Metric label={t('activeAlerts')} value={data.metrics.activeAlerts} icon={Bell} note={`${data.metrics.simulatedActiveAlerts} ${t('simulatedTag').toLowerCase()} · ${data.metrics.fieldActiveAlerts} ${t('fieldTag').toLowerCase()}`} critical={data.metrics.activeAlerts>0}/><Metric label={t('meanPressure')} value={data.metrics.averagePressureBar} suffix="bar" icon={Gauge} note={`${data.metrics.tankLevelPercent}% ${t('avgTankLevel')}`}/></div>
    <div className="dash-grid"><section className="panel chart-panel"><SectionHead title={t('waterLossExposure')} aside={<span className="soft-chip">{t('networkHealth')}</span>}/><div className="risk-layout"><div className="risk-score"><div className="eyebrow">{t('maintenanceRisk')}</div><strong><Status value={data.risk.level}/></strong><p>{data.risk.explanation}</p></div><div className="risk-factors">{data.risk.factors.map((f,i)=><div key={i}><span className="factor-num">0{i+1}</span><span>{f}</span><ArrowRight size={14}/></div>)}</div></div><div className="loss-ribbon"><div><span>{t('estWaterLoss')}</span><b className="font-data">{data.metrics.waterLossPercent}<small>%</small></b></div><div className="loss-bar"><span style={{width:`${Math.min(data.metrics.waterLossPercent,100)}%`}}/></div><span className="eyebrow">{t('aggregateEstimate')}</span></div>{simLoss.data && <div className="loss-ribbon" style={{marginTop: 12, borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: 10}}><div><span>{t('simulatedWaterLoss')}</span><b className="font-data">{simLoss.data.total_litres_lost ?? 0}<small>L</small></b></div><div style={{display:'flex', justifyContent:'space-between', alignItems:'center', width:'100%', marginTop:4}}><span className="soft-chip" style={{fontSize: 11}}>{t('simulatedEstimate')}</span><small style={{color: 'var(--text-muted, #64748b)', fontSize: 12}}>{simLoss.data.total_projected_saving_litres ?? 0}L {t('savedVsDelay')}</small></div></div>}</section>
     <section className="panel alerts-panel"><SectionHead title={t('recentAlerts')} aside={<NavLink to="/alerts" className="text-action">{t('allAlerts')} <ArrowRight size={14}/></NavLink>}/>{data.recentAlerts.length ? <div className="compact-list">{data.recentAlerts.slice(0,5).map(alert=><div className="compact-alert" key={alert.id}><span className={`alert-indicator ${alert.severity}`}>{alert.severity==='critical'?<AlertTriangle size={15}/>:<Activity size={15}/>}</span><div className="compact-main"><b>{alert.riskTitle || alert.type}</b><span>{alert.location} · {alert.zone} · {alert.simulated ? t('simulatedTag') : t('fieldTag')}</span></div><div className="compact-meta"><Status value={alert.riskTitle || alert.severity}/><small>{shortTime(alert.createdAt)}</small></div></div>)}</div> : <Empty title={t('noActiveAlerts')} detail={t('noActiveAlertsDetail')}/>}</section></div>
    <div className="dash-bottom" style={{gridTemplateColumns:'repeat(auto-fit, minmax(240px, 1fr))'}}><div className="panel bottom-callout"><div className="callout-icon"><MapIcon size={20}/></div><div><span className="eyebrow">{t('fieldView')}</span><b>{t('fieldViewTitle')}</b><p>{t('fieldViewDesc')}</p></div><NavLink to="/map" className="round-arrow"><ArrowRight size={18}/></NavLink></div><div className="panel bottom-callout"><div className="callout-icon amber"><ClipboardList size={20}/></div><div><span className="eyebrow">{t('preventiveCare')}</span><b>{t('preventiveCareTitle')}</b><p>{t('preventiveCareDesc')}</p></div><NavLink to="/maintenance" className="round-arrow"><ArrowRight size={18}/></NavLink></div><div className="panel bottom-callout"><div className="callout-icon" style={{background:'#e1f4ec',color:'#0d766e'}}><Leaf size={20}/></div><div><span className="eyebrow">ENVIRONMENTAL LCA</span><b>{t('sustainabilityTitle')}</b><p>{t('sustainabilityDesc')}</p></div><NavLink to="/sustainability" className="round-arrow"><ArrowRight size={18}/></NavLink></div></div>
  </>}</>;
}

function Alerts() {
  const { t } = useLanguage();
  const q=useGetAlerts({ query: { queryKey: getGetAlertsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const champs=useGetWaterChampions({ query: { queryKey: getGetWaterChampionsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const smsLog=useGetSmsLog({ query: { queryKey: getGetSmsLogQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const ack=useAcknowledgeAlert(); const assign=useAssignAlert(); const resolve=useResolveAlert(); const start=useStartAlertMaintenance(); const qc=useQueryClient();
  const [status,setStatus]=useState('all'); const [severity,setSeverity]=useState('all'); const [search,setSearch]=useState('');
  const [searchParams,setSearchParams]=useSearchParams();
  const alerts=q.data||[];
  const visible=alerts.filter(a=>(status==='all'||a.status===status)&&(severity==='all'||a.severity===severity)&&`${a.location} ${a.zone} ${a.type} ${a.sensorId} ${a.source}`.toLowerCase().includes(search.toLowerCase()));
  const focusedAlert=alerts.find(a=>a.id===searchParams.get('alertId'));
  const closeFocused=()=>{const next=new URLSearchParams(searchParams);next.delete('alertId');setSearchParams(next,{replace:true})};
  const refresh=()=>{[getGetAlertsQueryKey(),getGetDashboardQueryKey(),getGetSensorsQueryKey(),getGetMaintenanceQueryKey(),getGetWaterChampionsQueryKey(),getGetSmsLogQueryKey()].forEach(queryKey=>qc.invalidateQueries({queryKey}));};
  const invoke=(m:any,vars:any)=>m.mutate(vars,{onSuccess:refresh});
  const active=alerts.filter(a=>a.status!=='resolved');
  return <><PageTitle kicker={t('incidentResponse')} title={t('alertCentre')} detail={t('alertCentreDetail')} action={<span className="live-pill"><i/> {t('liveFeed')}</span>}/>
    <div className="alert-risk-summary">
      {(['low','medium','high'] as const).map(level=><div className={`risk-count risk-${level}`} key={level}><span>{t(level + 'Risk')}</span><b>{active.filter(a=>a.riskLevel===level).length}</b></div>)}
      <div className="risk-count risk-resolved"><span>{t('resolved')}</span><b>{alerts.filter(a=>a.status==='resolved').length}</b></div>
    </div>
    <section className="panel table-panel"><div className="table-toolbar"><div className="table-title"><h2 className="font-display">{t('alertLog')}</h2><span>{visible.length} {t('recordsCount')}</span></div><div className="table-filters"><div className="search-field"><Search size={15}/><input placeholder={t('findLocation')} value={search} onChange={e=>setSearch(e.target.value)}/></div><select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">{t('allStatus')}</option><option value="active">{t('active')}</option><option value="acknowledged">{t('acknowledged')}</option><option value="assigned">{t('assigned')}</option><option value="in_progress">{t('inProgress')}</option><option value="resolved">{t('resolved')}</option></select><select value={severity} onChange={e=>setSeverity(e.target.value)}><option value="all">{t('allSeverity')}</option><option value="critical">{t('critical')}</option><option value="warning">{t('warning')}</option></select></div></div>
    {q.isLoading?<Skeleton rows={6}/>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:visible.length===0?<Empty title={alerts.length?t('noAlertsMatch'):t('noAlertEventsYet')} detail={alerts.length?t('noAlertsFilterDetail'):t('noAlertEventsDetail')}/>:<div className="table-scroll"><table><thead><tr><th>{t('thRiskCondition')}</th><th>{t('thLocationZone')}</th><th>{t('thSensor')}</th><th>{t('thFlowPressure')}</th><th>{t('thSource')}</th><th>{t('thAssignee')}</th><th>{t('thStatus')}</th><th>{t('thResponse')}</th></tr></thead><tbody>{visible.map(a=><tr key={a.id}><td><div className="alert-type-cell"><span className={`alert-indicator ${a.severity}`}><AlertTriangle size={14}/></span><span><b>{a.riskTitle||a.type}</b><small>{a.type} · {dateTime(a.createdAt)}</small></span></div></td><td><b>{a.location}</b><small>{a.zone}</small></td><td className="font-data">{a.sensorId}</td><td className="font-data">{a.flowLpm} L/min <small>{a.pressureBar} bar</small></td><td><span className={`source-tag ${a.simulated?'source-simulated':'source-field'}`}>{a.simulated?t('simulatedTag'):t('fieldTag')}</span></td><td><select aria-label={`Assign ${a.id}`} value={a.championId||''} onChange={e=>e.target.value&&invoke(assign,{id:a.id,data:{championId:e.target.value}})}><option value="">{t('unassigned')}</option>{(champs.data||[]).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></td><td><Status value={a.status}/></td><td><div className="row-actions">{a.status==='active'&&<button onClick={()=>invoke(ack,{id:a.id})} title={t('titleAck')}><Check size={15}/> {t('btnAck')}</button>}{a.status!=='resolved'&&<button onClick={()=>invoke(start,{id:a.id,data:{priority:a.severity==='critical'?'critical':'high',championId:a.championId||undefined}})} title={t('titleStartMaint')}><Wrench size={14}/></button>}{a.status!=='resolved'&&<button onClick={()=>invoke(resolve,{id:a.id})} title={t('titleResolve')}><CheckCircle2 size={15}/></button>}</div></td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel sms-log-panel"><div className="table-toolbar"><div className="table-title"><h2 className="font-display">{t('mockSmsLog')}</h2><span>{t('noProviderConnected')}</span></div><span className="mock-only-label"><Smartphone size={14}/> {t('mockOnly')}</span></div>
      {smsLog.isError?<ErrorBox error={smsLog.error} retry={()=>smsLog.refetch()}/>:!smsLog.data?.length?<Empty title={t('noMockMessagesYet')} detail={t('noMockMessagesDetail')}/>:<div className="mock-sms-list">{smsLog.data.map(item=><article className="mock-sms-entry" key={item.id}><div className="mock-sms-head"><span className="mock-sms-label">Mock SMS</span><Status value={`${item.riskLevel} risk`}/><span className={`source-tag ${item.simulated?'source-simulated':'source-field'}`}>{item.simulated?t('simulatedTag'):t('fieldTag')}</span></div><b>{item.zone}</b><small>{item.recipient ? `${t('recipientLabel')} ${item.recipient}` : t('noRecipientAvailable')} · {dateTime(item.createdAt)}</small><p>{item.message}</p></article>)}</div>}
    </section>
    {[ack,assign,resolve,start].some(m=>m.isError)&&<div className="inline-error">{errorText(ack.error||assign.error||resolve.error||start.error)}</div>}
    {focusedAlert&&<div className="modal-backdrop" role="presentation" onMouseDown={e=>e.target===e.currentTarget&&closeFocused()}><section className="modal-card alert-detail-modal" role="dialog" aria-modal="true" aria-labelledby="alert-detail-title"><div className="modal-header"><div><span className="eyebrow">{focusedAlert.simulated?t('simulatedAlertModal'):t('fieldAlertModal')}</span><h2 className="font-display" id="alert-detail-title">{focusedAlert.riskTitle||focusedAlert.type}</h2></div><button type="button" className="icon-button" onClick={closeFocused} aria-label="Close alert"><X size={18}/></button></div><div className="alert-detail-grid"><div><span>{t('detailLocation')}</span><b>{focusedAlert.location}</b></div><div><span>{t('detailZone')}</span><b>{focusedAlert.zone}</b></div><div><span>{t('detailSensor')}</span><b>{focusedAlert.sensorId}</b></div><div><span>{t('detailStatus')}</span><b><Status value={focusedAlert.status}/></b></div><div><span>{t('detailFlow')}</span><b>{focusedAlert.flowLpm} L/min</b></div><div><span>{t('detailPressure')}</span><b>{focusedAlert.pressureBar} bar</b></div></div><p>{focusedAlert.message}</p>{focusedAlert.mockSmsMessage&&<div className="alert-detail-sms"><span className="mock-sms-label">Mock SMS</span><p>{focusedAlert.mockSmsMessage}</p></div>}<div className="modal-actions"><Button onClick={closeFocused}>{t('close')}</Button></div></section></div>}
  </>;
}

function PipelineMap() {
  const { t } = useLanguage();
  const p=useGetPipelines({ query: { queryKey: getGetPipelinesQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } }); const s=useGetSensors({ query: { queryKey: getGetSensorsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const fallback=[18.5204,73.8567] as [number,number];
  const segments=useMemo(()=>p.data||[],[p.data]);
  const mapSensors=useMemo(()=>[...new Map(segments.flatMap(pipe=>(pipe.sensors||[]).map(sensor=>[sensor.sensorId,{...sensor,location:pipe.location}] as const))).values()],[segments]);
  const center=segments[0]?.coordinates?.[0] ? [segments[0].coordinates[0][0],segments[0].coordinates[0][1]] as [number,number] : fallback;
  return <><PageTitle kicker={t('infrastructure')} title={t('navMap')} detail={t('mapDetail')} action={<span className="map-legend"><i className="legend-line"/> {t('legendPipeline')} <i className="legend-dot"/> {t('legendSensor')}</span>}/>
    <div className="map-layout">
      <section className="panel map-frame">
        {p.isLoading ? <div className="map-loading"><Skeleton rows={4}/></div> : p.isError ? <ErrorBox error={p.error} retry={()=>p.refetch()}/> :
          <MapContainer center={center} zoom={12} scrollWheelZoom className="leaflet-map">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
            {segments.map(pipe => <Polyline key={pipe.id} positions={pipe.coordinates as [number,number][]} pathOptions={{ color:pipe.status==='leak'?'#b8493f':pipe.status==='warning'?'#d09225':'#128884', weight:5, opacity:.82 }}>
              <Popup><b>{pipe.name}</b><br/>{pipe.location}<br/><Status value={pipe.status}/>{pipe.simulated&&<><br/><span className="source-tag source-simulated">{t('simulatedTag')}</span></>}</Popup>
            </Polyline>)}
            {mapSensors.map(sensor => <CircleMarker key={sensor.sensorId} center={sensor.coordinates as [number,number]} radius={sensor.status==='leak'?9:6} pathOptions={{ color:sensor.status==='leak'?'#b8493f':sensor.status==='warning'?'#d09225':'#147c77', fillColor:sensor.status==='leak'?'#b8493f':'#30a89a', fillOpacity:.95, weight:2 }}>
              <Popup><b>{sensor.sensorId}</b><br/>{sensor.location}<br/><Status value={sensor.status}/>{sensor.simulated&&<><br/><span className="source-tag source-simulated">{t('simulatedTag')}</span></>}</Popup>
            </CircleMarker>)}
          </MapContainer>}
      </section>
    <aside className="map-sidebar"><div className="map-aside-head"><div><span className="eyebrow">{t('networkAssets')}</span><h2 className="font-display">{t('fieldInventory')}</h2></div><span className="count-pill">{segments.length}</span></div><div className="map-stats"><div><span>{t('sensorNodes')}</span><b>{s.data?.length ?? '—'}</b></div><div><span>{t('activeRoutes')}</span><b>{segments.filter(x=>x.status!=='inactive').length}</b></div><div><span>{t('needsAttention')}</span><b className="attention-num">{segments.filter(x=>['leak','warning'].includes(x.status)).length}</b></div></div>
      <div className="map-list-title">{t('pipelineRoutes')}</div>{p.isLoading?<Skeleton rows={4}/>:segments.length?segments.map(pipe=><div className="pipeline-item" key={pipe.id}><span className={`route-marker ${pipe.status}`}/><div><b>{pipe.name}</b><small><MapPin size={12}/>{pipe.location}</small></div><Status value={pipe.status}/></div>):<Empty title={t('noRouteData')} detail={t('noRouteDataDetail')}/>}
      {s.isError&&<div className="map-error">{t('sensorTelemetryError')} {errorText(s.error)}</div>}
    </aside></div>
  </>;
}

function AnalyticsPage() {
  const { t } = useLanguage();
  const [range, setRange] = useState<'24h'|'7d'|'30d'>('7d');
  const [selectedZone, setSelectedZone] = useState<string>('Zone 1');
  const q = useGetAnalytics({range}, {query: {queryKey: getGetAnalyticsQueryKey({range})}});
  const a = q.data;

  // Fix Invalid Date on x-axis
  const labels = (timeStr: string) => {
    if (!timeStr) return '';
    const d = new Date(timeStr);
    if (isNaN(d.getTime())) return timeStr;
    if (range === '24h') {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } else if (range === '7d') {
      return d.toLocaleDateString([], { weekday: 'short', day: '2-digit' });
    } else {
      return d.toLocaleDateString([], { day: '2-digit', month: 'short' });
    }
  };

  return <><PageTitle kicker={t('networkIntelligence')} title={t('navAnalytics')} detail={t('analyticsDetail')} action={<div className="range-tabs">{(['24h','7d','30d'] as const).map(r=><button key={r} onClick={()=>setRange(r)} className={range===r?'selected':''}>{r}</button>)}</div>}/>
    {q.isLoading ? <div className="chart-grid">{[1,2,3,4].map(x=><div className="panel skeleton" style={{height:260}} key={x}/>)}</div> : q.isError ? <ErrorBox error={q.error} retry={()=>q.refetch()}/> : (!a || !a.kpis) ? <Empty title={t('noAnalytics')} detail={t('noAnalyticsDetail')}/> : <>
    <div className="analytics-overview">
      <div><span className="eyebrow">{t('reportingWindow')}</span><b>{range==='24h'?t('last24h'):range==='7d'?t('last7d'):t('last30d')}</b></div>
      <div><span className="eyebrow">{t('leakEventsUpper')}</span><b className="font-data">{a.kpis.leakEvents}</b></div>
      <div><span className="eyebrow">{t('meanResponseUpper')}</span><b className="font-data">{a.kpis.meanResponseMinutes}<small> min</small></b></div>
      <div><span className="eyebrow">{t('sensorsTrackedUpper')}</span><b className="font-data">{a.kpis.sensorsReporting} / {a.kpis.totalSensors}</b></div>
    </div>
    <div className="chart-grid">
      <ChartCard title={t('chartFlowPressure')} subtitle={t('subFlowPressure')}>
        <div style={{ position: 'absolute', top: '15px', right: '40px', zIndex: 10 }}>
          <select value={selectedZone} onChange={e => setSelectedZone(e.target.value)} style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc', fontSize: '12px' }}>
            {Array.from(new Set(a.flowPressure.map(fp => fp.zone))).map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={a.flowPressure.filter(fp => fp.zone === selectedZone)}>
            <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#dce7e4"/>
            <XAxis dataKey="time" tickFormatter={labels} tickLine={false} axisLine={false}/>
            <YAxis yAxisId="left" tickLine={false} axisLine={false} width={40}/>
            <YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} width={38}/>
            <Tooltip/>
            <Line yAxisId="left" type="monotone" dataKey="flowLpm" stroke="#128884" strokeWidth={2.5} dot={false}/>
            <Line yAxisId="right" type="monotone" dataKey="pressureBar" stroke="#d19a32" strokeWidth={2} dot={false}/>
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
      
      <ChartCard title={t('chartTankLevel')} subtitle={t('subTankLevel')}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={a.tankLevel}>
            <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#dce7e4"/>
            <XAxis dataKey="time" tickFormatter={labels} tickLine={false} axisLine={false}/>
            <YAxis domain={[0,100]} tickLine={false} axisLine={false}/>
            <Tooltip/>
            <Area type="monotone" dataKey="tankLevelPercent" stroke="#128884" fill="#bce3d7" strokeWidth={2}/>
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>
      
      <ChartCard title={t('simulatedWaterLostTitle', 'Simulated Water Lost')} subtitle={t('simulatedWaterLostSub', 'Estimated litres lost per zone')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={a.simulatedWaterLostPerZone}>
            <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#dce7e4"/>
            <XAxis dataKey="zone" tickLine={false} axisLine={false}/>
            <YAxis tickLine={false} axisLine={false}/>
            <Tooltip/>
            <Bar dataKey="litresLost" fill="#e0b350" radius={[4,4,0,0]} name="Litres Lost" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title={t('alertsByRiskTitle', 'Alerts by Risk')} subtitle={t('alertsByRiskSub', 'Low, medium, and high risk alerts over time')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={Object.values(a.alertsByRisk.reduce((acc, curr) => {
            if (!acc[curr.time]) acc[curr.time] = { time: curr.time, low: 0, medium: 0, high: 0 };
            acc[curr.time][curr.riskLevel] += curr.count;
            return acc;
          }, {} as Record<string, any>))}>
            <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#dce7e4"/>
            <XAxis dataKey="time" tickFormatter={labels} tickLine={false} axisLine={false}/>
            <YAxis tickLine={false} axisLine={false}/>
            <Tooltip/>
            <Bar dataKey="low" stackId="a" fill="#13867f" />
            <Bar dataKey="medium" stackId="a" fill="#d19a32" />
            <Bar dataKey="high" stackId="a" fill="#c45c4b" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title={t('alertsByZoneTitle', 'Alerts by Zone')} subtitle={t('alertsByZoneSub', 'Alert distribution across zones')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={a.alertsByZone} layout="vertical">
            <CartesianGrid strokeDasharray="3 4" horizontal={false} stroke="#dce7e4"/>
            <XAxis type="number" tickLine={false} axisLine={false}/>
            <YAxis dataKey="zone" type="category" width={82} tickLine={false} axisLine={false}/>
            <Tooltip/>
            <Bar dataKey="count" fill="#13867f" radius={[0,4,4,0]}/>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title={t('fieldResponseTitle', 'Field Response Time')} subtitle={t('fieldResponseSub', 'Average minutes to acknowledge or resolve')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={a.fieldResponse}>
            <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#dce7e4"/>
            <XAxis dataKey="championName" tickLine={false} axisLine={false}/>
            <YAxis tickLine={false} axisLine={false}/>
            <Tooltip/>
            <Bar dataKey="averageResponseMinutes" fill="#d19a32" radius={[4,4,0,0]} name="Avg Mins"/>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div></>}</>;
}
function ChartCard({title,subtitle,children}:any){return <section className="panel chart-card"><div className="chart-heading"><div><h2 className="font-display">{title}</h2><span className="eyebrow">{subtitle}</span></div><span className="chart-menu"><Activity size={15}/></span></div><div className="chart-body">{children}</div></section>}

function Maintenance() {
  const { t } = useLanguage();
  const q=useGetMaintenance({ query: { queryKey: getGetMaintenanceQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const champs=useGetWaterChampions({ query: { queryKey: getGetWaterChampionsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const create=useCreateMaintenance(); const update=useUpdateMaintenance(); const qc=useQueryClient();
  const [editing,setEditing]=useState<any>(null); const [showForm,setShowForm]=useState(false); const [search,setSearch]=useState('');
  const [form,setForm]=useState({pipeline:'',location:'',issue:'',championId:'',priority:'medium',status:'pending'});
  const records=q.data||[];
  const openCreate=()=>{setEditing(null);setForm({pipeline:'',location:'',issue:'',championId:'',priority:'medium',status:'pending'});setShowForm(true)};
  const openEdit=(r:any)=>{setEditing(r);setForm({pipeline:r.pipeline,location:r.location,issue:r.issue,championId:r.championId||'',priority:r.priority,status:r.status});setShowForm(true)};
  const save=(e:React.FormEvent)=>{e.preventDefault();const data={...form,championId:form.championId||null,priority:form.priority as any,status:form.status as any};const done=()=>{setShowForm(false);[getGetMaintenanceQueryKey(),getGetDashboardQueryKey()].forEach(queryKey=>qc.invalidateQueries({queryKey}))};if(editing)update.mutate({id:editing.id,data},{onSuccess:done});else create.mutate({data:data as any},{onSuccess:done})};
  const visible=records.filter(r=>`${r.pipeline} ${r.location} ${r.issue} ${r.championName}`.toLowerCase().includes(search.toLowerCase()));
  return <><PageTitle kicker={t('kickerWorkOrders')} title={t('navMaintenance')} detail={t('maintDetail')} action={<Button onClick={openCreate}><Plus size={17}/>{t('newRepair')}</Button>}/>
    <div className="work-summary"><div><span>{t('openRepairs')}</span><b>{records.filter(r=>r.status!=='completed').length}</b></div><div><span>{t('inProgressUpper')}</span><b>{records.filter(r=>r.status==='in-progress').length}</b></div><div><span>{t('completedRepairsUpper')}</span><b>{records.filter(r=>r.status==='completed').length}</b></div><div><span>{t('awaitingAssignment')}</span><b>{records.filter(r=>!r.championId).length}</b></div></div>
    <section className="panel table-panel"><div className="table-toolbar"><div className="table-title"><h2 className="font-display">{t('repairRegister')}</h2><span>{visible.length} {t('recordsCount')}</span></div><div className="search-field"><Search size={15}/><input placeholder={t('searchRepairsPlaceholder')} value={search} onChange={e=>setSearch(e.target.value)}/></div></div>
      {q.isLoading?<Skeleton rows={5}/>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:visible.length===0?<Empty title={records.length?t('noWorkOrdersMatch'):t('noRepairWorkOrders')} detail={records.length?t('changeSearchTerms'):t('createRepairDesc')}/>:<div className="table-scroll"><table><thead><tr><th>{t('thWorkOrder')}</th><th>{t('thPipelineLocation')}</th><th>{t('thIssue')}</th><th>{t('thChampion')}</th><th>{t('thPriority')}</th><th>{t('thStatus')}</th><th>{t('thStarted')}</th><th></th></tr></thead><tbody>{visible.map(r=><tr key={r.id}><td><b className="font-data">{r.maintenanceId}</b></td><td><b>{r.pipeline}</b><small>{r.location}</small></td><td>{r.issue}</td><td>{r.championName||t('unassigned')}</td><td><Status value={r.priority}/></td><td><Status value={r.status}/></td><td>{dateTime(r.startedAt)}</td><td><button className="icon-button" title={t('editRepair')} onClick={()=>openEdit(r)}><Pencil size={15}/></button></td></tr>)}</tbody></table></div>}
    </section>
    {showForm&&<div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&setShowForm(false)}><form className="modal-card" onSubmit={save}><div className="modal-header"><div><span className="eyebrow">{editing?t('modalUpdateExisting'):t('modalNewWorkOrder')}</span><h2 className="font-display">{editing?t('editRepair'):t('createRepair')}</h2></div><button type="button" className="icon-button" onClick={()=>setShowForm(false)}><X size={18}/></button></div><label>{t('pipelineLabel')}<input required value={form.pipeline} onChange={e=>setForm({...form,pipeline:e.target.value})}/></label><label>{t('locationLabel')}<input required value={form.location} onChange={e=>setForm({...form,location:e.target.value})}/></label><label>{t('issueDescLabel')}<textarea required rows={3} value={form.issue} onChange={e=>setForm({...form,issue:e.target.value})}/></label><div className="form-grid"><label>{t('assignChampionLabel')}<select value={form.championId} onChange={e=>setForm({...form,championId:e.target.value})}><option value="">{t('unassigned')}</option>{(champs.data||[]).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label>{t('priorityLabel')}<select value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}>{['low','medium','high','critical'].map(x=><option key={x} value={x}>{t('status_' + x, x)}</option>)}</select></label><label>{t('statusLabel')}<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>{['pending','assigned','in-progress','completed'].map(x=><option key={x} value={x}>{t('status_' + x.replace('-','_'), x)}</option>)}</select></label></div>{(create.isError||update.isError)&&<div className="inline-error">{errorText(create.error||update.error)}</div>}<div className="modal-actions"><Button type="button" variant="quiet" onClick={()=>setShowForm(false)}>{t('cancel')}</Button><Button disabled={create.isPending||update.isPending}><Save size={16}/>{create.isPending||update.isPending?t('saving'):t('saveRepair')}</Button></div></form></div>}
  </>;
}

function Champions() {
  const { t } = useLanguage();
  const q=useGetWaterChampions({ query: { queryKey: getGetWaterChampionsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } });
  const people=q.data||[];
  return <><PageTitle kicker={t('kickerFieldResponse')} title={t('navChampions')} detail={t('championsDetail')} action={<span className="soft-chip"><Users size={14}/> {people.length} {t('fieldTeamCount')}</span>}/>
    <div className="champion-overview"><div className="champion-note"><span className="eyebrow">{t('fieldCoverage')}</span><b>{t('championsHeroBold')}</b><p>{t('championsHeroDesc')}</p></div><div className="coverage-stat"><div className="coverage-ring"><strong>{people.filter(x=>x.status==='available').length}</strong><span>{t('status_available')}</span></div><div className="coverage-key"><div><i className="key-available"/> {t('status_available')} <b>{people.filter(x=>x.status==='available').length}</b></div><div><i className="key-onsite"/> {t('status_on_site')} <b>{people.filter(x=>x.status==='on-site').length}</b></div><div><i className="key-off"/> {t('status_off_duty')} <b>{people.filter(x=>x.status==='off-duty').length}</b></div></div></div></div>
    <SectionHead title={t('fieldTeam')} aside={<span className="eyebrow">{t('championsAside')}</span>}/>
    {q.isLoading?<div className="champion-grid">{[1,2,3].map(x=><div key={x} className="panel skeleton" style={{height:220}}/>)}</div>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:people.length===0?<Empty title={t('noChampionsTitle')} detail={t('noChampionsDesc')}/>:<div className="champion-grid">{people.map((c,i)=><article key={c.id} className="panel champion-card"><div className="champion-card-top"><div className={`champion-avatar avatar-tone-${i%4}`}>{c.name.split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase()}</div><div className="champion-identity"><h3>{c.name}</h3><span><MapPin size={13}/>{c.assignedZone}</span></div><Status value={c.status}/></div><a className="champion-phone" href={`tel:${c.phone}`}><Phone size={14}/>{c.phone}</a><div className="champion-stats"><div><span>{t('activeAlertsUpper')}</span><b className="font-data">{c.activeAlerts}</b></div><div><span>{t('repairsClosed')}</span><b className="font-data">{c.completedRepairs}</b></div><div><span>{t('avgResponse')}</span><b className="font-data">{c.averageResponseMinutes}<small> min</small></b></div></div><div className="champion-foot"><span><Clock3 size={13}/> {t('responsePerformance')}</span><div className="response-track"><i style={{width:`${Math.max(16,Math.min(100,100-c.averageResponseMinutes))}%`}}/></div></div></article>)}</div>}
  </>;
}

function Reports() {
  const { t } = useLanguage();
  const [type,setType]=useState('water-usage'); const [from,setFrom]=useState(new Date(Date.now()-7*86400000).toISOString().slice(0,10)); const [to,setTo]=useState(new Date().toISOString().slice(0,10));
  const params={type:type as any,from,to}; const enabled=!!from&&!!to&&from<=to;
  const q=useGetReport(params,{query:{queryKey:getGetReportQueryKey(params),enabled}});
  const r=q.data;
  const exportCsv=()=>{if(!r)return;const esc=(v:string)=>`"${String(v).replaceAll('"','""')}"`;const csv=[r.columns.map(esc).join(','),...r.rows.map(row=>row.map(esc).join(','))].join('\r\n');const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));link.download=`${type}-${from}-${to}.csv`;link.click();URL.revokeObjectURL(link.href)};
  return <><PageTitle kicker={t('kickerOpRecords')} title={t('navReports')} detail={t('reportsDetail')} action={<Button disabled={!r} onClick={exportCsv}><Download size={16}/>{t('exportCsv')}</Button>}/>
    <section className="panel report-controls"><div className="report-filter-title"><span className="filter-icon"><Filter size={17}/></span><div><b>{t('configureReport')}</b><small>{t('reportSubtitle')}</small></div></div><label>{t('reportType')}<select value={type} onChange={e=>setType(e.target.value)}>{[['water-usage','reportWaterUsage'],['water-loss','reportWaterLoss'],['leak-events','reportLeakEvents'],['pipeline-health','reportPipelineHealth'],['sensor-health','reportSensorHealth'],['maintenance','reportMaintenance']].map(([v,k])=><option value={v} key={v}>{t(k)}</option>)}</select></label><label>{t('fromDate')}<input type="date" value={from} max={to} onChange={e=>setFrom(e.target.value)}/></label><label>{t('toDate')}<input type="date" value={to} min={from} onChange={e=>setTo(e.target.value)}/></label></section>
    <section className="panel report-preview"><div className="report-preview-head"><div><span className="eyebrow">{t('reportPreview')}</span><h2 className="font-display">{r?.title||t('preparingReport')}</h2></div>{r&&<span className="soft-chip"><CalendarDays size={14}/>{r.from} — {r.to}</span>}</div>
    {!enabled?<div className="inline-error">{t('invalidDateRange')}</div>:q.isLoading?<Skeleton rows={6}/>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:r?.rows.length?<><div className="table-scroll"><table><thead><tr>{r.columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{r.rows.slice(0,25).map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j}>{cell}</td>)}</tr>)}</tbody></table></div><div className="report-foot">{r.rows.length} {t('rowsCount')} · {t('generatedAt')} {dateTime(r.generatedAt)}{r.rows.length>25?` · ${t('previewLimited')}`:''}</div></>:<Empty title={t('noReportRows')} detail={t('noReportRowsDetail')}/>}</section>
  </>;
}

function Profile() {
  const { t } = useLanguage();
  const q=useGetProfile(); const update=useUpdateProfile(); const qc=useQueryClient();
  const [form,setForm]=useState<any>(null); const [saved,setSaved]=useState(false);
  if(q.data&&!form)setForm({...q.data});
  const save=(e:React.FormEvent)=>{e.preventDefault();update.mutate({data:{fullName:form.fullName,email:form.email,mobile:form.mobile,assignedZone:form.assignedZone}},{onSuccess:(profile)=>{setForm({...profile});setSaved(true);qc.invalidateQueries({queryKey:getGetProfileQueryKey()});qc.invalidateQueries({queryKey:getGetAuthSessionQueryKey()})}})};
  return <><PageTitle kicker={t('kickerAccount')} title={t('navProfile')} detail={t('profileDetail')}/>
    {q.isLoading?<div className="panel profile-panel"><Skeleton rows={5}/></div>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:form&&<div className="profile-layout"><section className="panel profile-panel"><div className="profile-intro"><div className="profile-avatar">{form.fullName.split(' ').map((x:string)=>x[0]).slice(0,2).join('').toUpperCase()}</div><div><span className="eyebrow">{t('currentAccount')}</span><h2 className="font-display">{form.fullName}</h2><Status value={form.role}/></div></div><form className="profile-form" onSubmit={save}><div className="form-grid"><label>{t('fullName')}<input required minLength={2} maxLength={120} value={form.fullName} onChange={e=>setForm({...form,fullName:e.target.value})}/></label><label>{t('emailAddress')}<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>{t('mobileNumber')}<input required minLength={8} maxLength={24} value={form.mobile} onChange={e=>setForm({...form,mobile:e.target.value})}/></label><label>{t('assignedZone')}<input value={form.assignedZone||''} onChange={e=>setForm({...form,assignedZone:e.target.value})}/></label></div>{(update.isError)&&<div className="inline-error">{errorText(update.error)}</div>}{saved&&<div className="success-note"><CheckCircle2 size={16}/> {t('profileSaved')}</div>}<div className="modal-actions"><Button disabled={update.isPending}><Save size={16}/>{update.isPending?t('saving'):t('saveChanges')}</Button></div></form></section><aside className="panel account-note"><ShieldCheck size={23}/><span className="eyebrow">{t('accountSecurity')}</span><h3 className="font-display">{t('managedSecurely')}</h3><p>{t('securityNotice')}</p><div className="account-meta"><span>{t('accountId')}</span><b className="font-data">{form.id}</b></div><div className="account-meta"><span>{t('roleLabel')}</span><b><Status value={form.role}/></b></div></aside></div>}
  </>;
}

function SettingsPage() {
  const { t } = useLanguage();
  const q=useGetSettings({ query: { queryKey: getGetSettingsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } }); const update=useUpdateSettings(); const qc=useQueryClient();
  const [form,setForm]=useState<any>(null);
  if(q.data&&!form)setForm({...q.data});
  const save=(e:React.FormEvent)=>{e.preventDefault();update.mutate({data:{flowWarningThreshold:Number(form.flowWarningThreshold),flowLeakThreshold:Number(form.flowLeakThreshold),pressureWarningThreshold:Number(form.pressureWarningThreshold),pressureCriticalThreshold:Number(form.pressureCriticalThreshold)}},{onSuccess:(result)=>{setForm({...result});qc.invalidateQueries({queryKey:getGetSettingsQueryKey()})}})};
  return <><PageTitle kicker={t('kickerNetConfig')} title={t('navSettings')} detail={t('settingsDetail')}/>
    {q.isLoading?<div className="settings-grid"><div className="panel skeleton" style={{height:340}}/></div>:q.isError?<ErrorBox error={q.error} retry={()=>q.refetch()}/>:form&&<div className="settings-grid">
      <form className="panel settings-card" onSubmit={save}>
        <div className="settings-heading"><div className="settings-icon"><Gauge size={18}/></div><div><h2 className="font-display">{t('alertThresholds')}</h2><p>{t('thresholdsApplyNotice')}</p></div></div>
        <div className="threshold-group"><div className="threshold-heading"><span>{t('flowRateUpper')}</span><small>{t('flowUnit')}</small></div>
          <label>{t('warningThreshold')}<input type="number" step="0.1" min="0" value={form.flowWarningThreshold} onChange={e=>setForm({...form,flowWarningThreshold:e.target.value})}/></label>
          <label>{t('leakThreshold')}<input type="number" step="0.1" min="0" value={form.flowLeakThreshold} onChange={e=>setForm({...form,flowLeakThreshold:e.target.value})}/></label>
        </div>
        <div className="threshold-group"><div className="threshold-heading"><span>{t('pressureUpper')}</span><small>{t('pressureUnit')}</small></div>
          <label>{t('warningThreshold')}<input type="number" step="0.1" min="0" value={form.pressureWarningThreshold} onChange={e=>setForm({...form,pressureWarningThreshold:e.target.value})}/></label>
          <label>{t('criticalThreshold')}<input type="number" step="0.1" min="0" value={form.pressureCriticalThreshold} onChange={e=>setForm({...form,pressureCriticalThreshold:e.target.value})}/></label>
        </div>
        {update.isError&&<div className="inline-error">{errorText(update.error)}</div>}
        <div className="modal-actions"><Button disabled={update.isPending}><Save size={16}/>{update.isPending?t('saving'):t('saveThresholds')}</Button></div>
      </form>
      <section className="panel settings-card"><div className="settings-heading"><div className="settings-icon"><Radio size={18}/></div><div><h2 className="font-display">{t('esp32Sensors')}</h2><p>{t('registeredDevices')}</p></div></div>
         {form.devices?.length?<div className="device-list">{form.devices.map((d:any)=><div className="device-row" key={d.id}><span className="device-icon"><Zap size={16}/></span><div className="device-main"><b>{d.name}</b><small>{d.location} · {t('lastSeen')} {dateTime(d.lastSeen)}{d.simulated?` · ${t('simulatedTag')}`:''}</small></div><Status value={d.status}/></div>)}</div>:<Empty title={t('noDevices')} detail={t('noDevicesDetail')}/>}
      </section>
      <p className="field-note">{t('extNotifNote')}</p>
    </div>}
  </>;
}

function Simulation() {
  const sensors=useGetSensors({ query: { queryKey: getGetSensorsQueryKey(), refetchInterval: 2000, refetchIntervalInBackground: true } }); const submit=useSubmitSensorReading(); const qc=useQueryClient();
  const [form,setForm]=useState({sensorId:'',flowLpm:'8.6',pressureBar:'3.0',tankLevelPercent:'62'});
  const [result,setResult]=useState<any>(null);
  if(sensors.data?.length&&!form.sensorId)setForm(f=>({...f,sensorId:sensors.data![0].sensorId}));
  const setPreset=(mode:string)=>setForm(f=>mode==='NORMAL'?{...f,flowLpm:'8.6',pressureBar:'3.0',tankLevelPercent:'62'}:mode==='WARNING'?{...f,flowLpm:'13.5',pressureBar:'2.4',tankLevelPercent:'47'}:{...f,flowLpm:'18.6',pressureBar:'1.8',tankLevelPercent:'23'});
  const fire=(e:React.FormEvent)=>{e.preventDefault();setResult(null);submit.mutate({data:{sensorId:form.sensorId,flowLpm:Number(form.flowLpm),pressureBar:Number(form.pressureBar),tankLevelPercent:Number(form.tankLevelPercent),deviceId:'SIMULATION',simulatorId:getSimulatorId()}},{onSuccess:r=>{setResult(r);[getGetSensorsQueryKey(),getGetAlertsQueryKey(),getGetDashboardQueryKey(),getGetPipelinesQueryKey(),getGetMaintenanceQueryKey(),getGetWaterChampionsQueryKey(),getGetSmsLogQueryKey()].forEach(queryKey=>qc.invalidateQueries({queryKey}))}})};
  return <><PageTitle kicker={t('simKicker', 'HARDWARE DEMONSTRATION')} title={t('simTitle', 'Sensor simulation')} detail={t('simDetail', 'Submit a reading to exercise live threshold rules and backend alert workflows.')} action={<span className="soft-chip"><Radio size={14}/> {t('simCompatible', 'ESP32 COMPATIBLE')}</span>}/>
    <div className="simulation-layout"><section className="panel sim-intro"><div className="sim-illustration"><div className="sim-ring ring-one"/><div className="sim-ring ring-two"/><div className="sim-device"><Radio size={28}/><span>HG / 32</span></div><div className="sim-reading r-one"><span className="live-pulse"/> {t('simFlowInput', 'FLOW INPUT')}</div><div className="sim-reading r-two">{t('simPressureInput', 'PRESSURE INPUT')}</div></div><span className="eyebrow">{t('simLab', 'FIELD DEVICE LAB')}</span><h2 className="font-display">{t('simTestHeading', 'Test a reading.')}<br/><i>{t('simSeeResponse', 'See the response.')}</i></h2><p>{t('simTestDesc', 'Send a reading to the backend to test the configured rules and alert workflow.')}</p><div className="protocol-points"><div><Check size={15}/> {t('simPoint1', 'Reading is processed by the API')}</div><div><Check size={15}/> {t('simPoint2', 'Rule-based alerts are evaluated server-side')}</div><div><Check size={15}/> {t('simPoint3', 'External notifications are disabled')}</div></div></section>
    <section className="panel sim-form"><div className="sim-form-head"><span className="eyebrow">{t('simNewReading', 'NEW SENSOR READING')}</span><h2 className="font-display">{t('simCompose', 'Compose a test')}</h2><p>{t('simComposeDesc', 'Choose one of the sensor presets, then submit to the network.')}</p></div><div className="preset-row"><button type="button" onClick={()=>setPreset('NORMAL')} className="preset"><i className="preset-dot normal"/>{t('simNormal', 'NORMAL')}</button><button type="button" onClick={()=>setPreset('WARNING')} className="preset"><i className="preset-dot warning"/>{t('simWarning', 'WARNING')}</button><button type="button" onClick={()=>setPreset('LEAK')} className="preset"><i className="preset-dot leak"/>{t('simLeak', 'LEAK')}</button></div><form className="sim-reading-form" onSubmit={fire}><label>{t('simSensorId', 'Sensor ID')}<select required value={form.sensorId} onChange={e=>setForm({...form,sensorId:e.target.value})}>{sensors.data?.map(s=><option key={s.sensorId} value={s.sensorId}>{s.sensorId} · {s.location}</option>)}</select>{sensors.isError&&<small className="field-note">{t('simListError', 'Sensor list unavailable:')} {errorText(sensors.error)}</small>}</label><div className="form-grid"><label><span>{t('simFlowRate', 'Flow rate')} <small>L/min</small></span><input type="number" min="0" max="500" step="0.1" required value={form.flowLpm} onChange={e=>setForm({...form,flowLpm:e.target.value})}/></label><label><span>{t('simPressure', 'Pressure')} <small>bar</small></span><input type="number" min="0" max="20" step="0.1" required value={form.pressureBar} onChange={e=>setForm({...form,pressureBar:e.target.value})}/></label><label><span>{t('simTankLevel', 'Tank level')} <small>%</small></span><input type="number" min="0" max="100" step="0.1" required value={form.tankLevelPercent} onChange={e=>setForm({...form,tankLevelPercent:e.target.value})}/></label></div>{sensors.isLoading&&<div className="field-note">{t('simLoading', 'Loading available sensor devices…')}</div>}{submit.isError&&<div className="inline-error">{errorText(submit.error)}</div>}<Button disabled={submit.isPending||sensors.isLoading||!form.sensorId}>{submit.isPending?t('simSubmitting', 'Submitting reading…'):t('simSubmitBtn', 'Submit sensor reading')}<ArrowRight size={17}/></Button></form>
       {result&&<div className="simulation-result"><div className="result-top"><div><span className="eyebrow">{t('simBackendResp', 'BACKEND RESPONSE · SIMULATED')}</span><h3><Status value={result.alert?.riskTitle||result.pipelineStatus}/></h3></div><span className="result-time">{dateTime(result.reading?.lastUpdated)}</span></div><p>{result.message}</p><div className="result-details"><div><span>{t('simAlertHead', 'ALERT')}</span><b>{result.alertStatus?human(result.alertStatus):t('simNotTriggered', 'Not triggered')}</b></div><div><span>{t('simNotifHead', 'NOTIFICATIONS')}</span><b>{result.notificationsStatus==='mock_sent'?t('simMockLogged', 'Mock SMS logged'):t('simNoMsg', 'No message sent')}</b></div></div>{result.alert&&<div className="result-alert"><AlertTriangle size={15}/>{result.alert.riskTitle||result.alert.type} · {result.alert.location} · {t('simulatedTag')}</div>}{result.mockSms?.message&&<div className="alert-detail-sms"><span className="mock-sms-label">{t('mockSms')}</span><p>{result.mockSms.message}</p></div>}</div>}
    </section></div>
  </>;
}

function SustainabilityPage() {
  const { t } = useLanguage();
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('hg_access_token') : null;
  const simLoss = useQuery({
    queryKey: ['simulated-water-loss'],
    queryFn: async () => {
      const res = await fetch(apiUrl('/api/simulation/water-loss'), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });

  const [activeTab, setActiveTab] = useState<'carbon' | 'water' | 'energy'>('carbon');

  const liveExtraWaterSaved = simLoss.data?.total_litres_lost ? Math.round(simLoss.data.total_litres_lost) : 0;
  const totalWaterSavedMonth = 12450 + liveExtraWaterSaved;
  const carbonBaselineKg = 58.0;
  const carbonWithHydroGuardKg = 42.6;
  const energyBaselineKwh = 25.0;
  const energyWithHydroGuardKwh = 18.4;
  const waterLossBaselineL = 18500;

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <NavLink to="/dashboard" className="text-action">
          <ArrowLeft size={16} /> {t('backToOverview')}
        </NavLink>
      </div>

      <PageTitle
        kicker={t('lcaKicker')}
        title={t('lcaTitle')}
        detail={t('lcaDetail')}
        action={
          <div className="lca-tabs">
            <button
              type="button"
              className={`lca-tab ${activeTab === 'carbon' ? 'active' : ''}`}
              onClick={() => setActiveTab('carbon')}
            >
              {t('tabCarbon')}
            </button>
            <button
              type="button"
              className={`lca-tab ${activeTab === 'water' ? 'active' : ''}`}
              onClick={() => setActiveTab('water')}
            >
              {t('tabWater')}
            </button>
            <button
              type="button"
              className={`lca-tab ${activeTab === 'energy' ? 'active' : ''}`}
              onClick={() => setActiveTab('energy')}
            >
              {t('tabEnergy')}
            </button>
          </div>
        }
      />

      <div className="lca-banner">
        <div>
          <span className="lca-badge-pill">
            <Sparkles size={13} /> {t('verifiedStandard')}
          </span>
          <h2>{t('bannerTitle')}</h2>
          <p>{t('bannerDesc')}</p>
        </div>
        <div style={{ textAlign: 'right', minWidth: 150 }}>
          <span style={{ fontSize: 10, color: '#a7d5c7', fontFamily: 'var(--app-font-mono)' }}>{t('netAbatement')}</span>
          <div style={{ font: '700 28px var(--app-font-mono)', color: '#6ee7b7' }}>-15.4 <small style={{ fontSize: 13 }}>kg CO₂e</small></div>
          <small style={{ fontSize: 10, color: '#9ec4b7' }}>{t('perMonitoredSystem')}</small>
        </div>
      </div>

      <div className="lca-hero-grid">
        <div className="lca-card">
          <div className="lca-card-top">
            <span className="eyebrow">{t('carbonFootprint')}</span>
            <div className="lca-card-icon"><Globe size={18} /></div>
          </div>
          <div>
            <div className="lca-value">
              42.6 <small>kg CO₂e</small>
            </div>
            <span style={{ fontSize: 11, color: '#68827c' }}>{t('perSystemYear')}</span>
          </div>
          <div className="lca-card-foot">
            <span className="lca-delta-pill">▼ 26.6% vs legacy</span>
            <span>{t('embodiedLca')}</span>
          </div>
        </div>

        <div className="lca-card">
          <div className="lca-card-top">
            <span className="eyebrow">{t('metricEnergy').toUpperCase()}</span>
            <div className="lca-card-icon amber"><Zap size={18} /></div>
          </div>
          <div>
            <div className="lca-value">
              18.4 <small>kWh</small>
            </div>
            <span style={{ fontSize: 11, color: '#68827c' }}>{t('energyLoad')}</span>
          </div>
          <div className="lca-card-foot">
            <span className="lca-delta-pill">▼ 26.4% reduction</span>
            <span>{t('solarAssisted')}</span>
          </div>
        </div>

        <div className="lca-card">
          <div className="lca-card-top">
            <span className="eyebrow">{t('waterConserved')}</span>
            <div className="lca-card-icon blue"><Droplets size={18} /></div>
          </div>
          <div>
            <div className="lca-value">
              {totalWaterSavedMonth.toLocaleString()} <small>Litres</small>
            </div>
            <span style={{ fontSize: 11, color: '#68827c' }}>{t('conservedMonth')}</span>
          </div>
          <div className="lca-card-foot">
            <span className="lca-delta-pill">▼ 67.3% loss prevented</span>
            <span>{simLoss.data ? 'Live simulated' : 'Triage active'}</span>
          </div>
        </div>

        <div className="lca-card">
          <div className="lca-card-top">
            <span className="eyebrow">{t('designLifespan').toUpperCase()}</span>
            <div className="lca-card-icon purple"><Clock3 size={18} /></div>
          </div>
          <div>
            <div className="lca-value">
              7.0 <small>Years</small>
            </div>
            <span style={{ fontSize: 11, color: '#68827c' }}>{t('designLifespan')}</span>
          </div>
          <div className="lca-card-foot">
            <span>Electronic waste</span>
            <b style={{ font: '600 12px var(--app-font-mono)', color: '#234d49' }}>{t('eWaste')}</b>
          </div>
        </div>
      </div>

      <div className="sustainability-grid">
        <div style={{ display: 'grid', gap: 18 }}>
          <section className="panel comparison-panel">
            <SectionHead
              title={t('compTitle')}
              aside={<span className="soft-chip"><TrendingDown size={13} /> {t('compAside')}</span>}
            />
            <p style={{ fontSize: 12, color: '#6a827c', margin: '0 0 12px', lineHeight: 1.5 }}>
              {t('compIntro')}
            </p>

            <div className="comp-table-wrap">
              <table className="comp-table">
                <thead>
                  <tr>
                    <th>{t('thMetric')}</th>
                    <th>{t('thWithout')}</th>
                    <th>{t('thWith')}</th>
                    <th>{t('thNetBenefit')}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Droplets size={15} color="#0284c7" /> {t('metricWaterLoss')}
                      </b>
                      <small style={{ color: '#82948e' }}>{t('subWaterLoss')}</small>
                    </td>
                    <td>
                      <span className="comp-badge-legacy">{waterLossBaselineL.toLocaleString()} L</span>
                    </td>
                    <td>
                      <span className="comp-badge-active">{totalWaterSavedMonth.toLocaleString()} L saved</span>
                    </td>
                    <td>
                      <span className="comp-badge-save">▼ 67.3% reduction</span>
                    </td>
                  </tr>

                  <tr>
                    <td>
                      <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Zap size={15} color="#d97706" /> {t('metricEnergy')}
                      </b>
                      <small style={{ color: '#82948e' }}>{t('subEnergy')}</small>
                    </td>
                    <td>
                      <span className="comp-badge-legacy">{energyBaselineKwh.toFixed(1)} kWh/yr</span>
                    </td>
                    <td>
                      <span className="comp-badge-active">{energyWithHydroGuardKwh.toFixed(1)} kWh/yr</span>
                    </td>
                    <td>
                      <span className="comp-badge-save">▼ 26.4% energy saved</span>
                    </td>
                  </tr>

                  <tr>
                    <td>
                      <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Globe size={15} color="#059669" /> {t('metricCarbon')}
                      </b>
                      <small style={{ color: '#82948e' }}>{t('subCarbon')}</small>
                    </td>
                    <td>
                      <span className="comp-badge-legacy">{carbonBaselineKg.toFixed(1)} kg CO₂e</span>
                    </td>
                    <td>
                      <span className="comp-badge-active">{carbonWithHydroGuardKg.toFixed(1)} kg CO₂e</span>
                    </td>
                    <td>
                      <span className="comp-badge-save">▼ 15.4 kg abated/yr</span>
                    </td>
                  </tr>

                  <tr>
                    <td>
                      <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Clock3 size={15} color="#7c3aed" /> {t('metricTriage')}
                      </b>
                      <small style={{ color: '#82948e' }}>{t('subTriage')}</small>
                    </td>
                    <td>
                      <span className="comp-badge-legacy">360 mins (manual)</span>
                    </td>
                    <td>
                      <span className="comp-badge-active">&lt; 20 mins (alerted)</span>
                    </td>
                    <td>
                      <span className="comp-badge-save">18x faster response</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel" style={{ padding: 22 }}>
            <SectionHead
              title={t('envBenefitsTitle')}
              aside={<span className="soft-chip">{t('circularSystem')}</span>}
            />
            <div className="benefits-grid">
              <div className="benefit-card">
                <div className="benefit-icon-check"><Check size={16} /></div>
                <div>
                  <h4>{t('solarSensors')}</h4>
                  <p>{t('solarSensorsDesc')}</p>
                </div>
              </div>

              <div className="benefit-card">
                <div className="benefit-icon-check"><Check size={16} /></div>
                <div>
                  <h4>{t('lowPowerComms')}</h4>
                  <p>{t('lowPowerCommsDesc')}</p>
                </div>
              </div>

              <div className="benefit-card">
                <div className="benefit-icon-check"><Check size={16} /></div>
                <div>
                  <h4>{t('reducedWaste')}</h4>
                  <p>{t('reducedWasteDesc')}</p>
                </div>
              </div>

              <div className="benefit-card">
                <div className="benefit-icon-check"><Check size={16} /></div>
                <div>
                  <h4>{t('longerLife')}</h4>
                  <p>{t('longerLifeDesc')}</p>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="panel climate-ring-panel">
          <SectionHead
            title={t('lcaBreakdown')}
            aside={<span className="soft-chip">{t('stageShare')}</span>}
          />

          <div style={{ position: 'relative', width: 220, height: 220, margin: '15px 0' }}>
            <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
              <circle cx="50" cy="50" r="38" fill="none" stroke="#e6eee8" strokeWidth="11" />
              <circle
                cx="50"
                cy="50"
                r="38"
                fill="none"
                stroke="#0d766e"
                strokeWidth="11"
                strokeDasharray="104 135"
                strokeDashoffset="0"
                strokeLinecap="round"
              />
              <circle
                cx="50"
                cy="50"
                r="38"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="11"
                strokeDasharray="68 171"
                strokeDashoffset="-108"
                strokeLinecap="round"
              />
              <circle
                cx="50"
                cy="50"
                r="38"
                fill="none"
                stroke="#f59e0b"
                strokeWidth="11"
                strokeDasharray="33 206"
                strokeDashoffset="-180"
                strokeLinecap="round"
              />
              <circle
                cx="50"
                cy="50"
                r="38"
                fill="none"
                stroke="#10b981"
                strokeWidth="11"
                strokeDasharray="21 218"
                strokeDashoffset="-217"
                strokeLinecap="round"
              />
            </svg>

            <div className="climate-ring-center">
              <span className="eyebrow">LIFECYCLE TOTAL</span>
              <strong>42.6</strong>
              <span>kg CO₂e/yr</span>
            </div>
          </div>

          <div className="breakdown-list">
            <div className="breakdown-row">
              <div className="breakdown-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 8, height: 8, borderRadius: '50%', background: '#0d766e', display: 'inline-block' }} />
                  <b>{t('stageManufacturing')}</b>
                </span>
                <span>45% · 19.2 kg</span>
              </div>
              <div className="breakdown-track">
                <div className="breakdown-fill fill-manuf" style={{ width: '45%' }} />
              </div>
            </div>

            <div className="breakdown-row">
              <div className="breakdown-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }} />
                  <b>{t('stageElectronics')}</b>
                </span>
                <span>30% · 12.8 kg</span>
              </div>
              <div className="breakdown-track">
                <div className="breakdown-fill fill-electr" style={{ width: '30%' }} />
              </div>
            </div>

            <div className="breakdown-row">
              <div className="breakdown-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                  <b>{t('stageTransport')}</b>
                </span>
                <span>15% · 6.4 kg</span>
              </div>
              <div className="breakdown-track">
                <div className="breakdown-fill fill-transp" style={{ width: '15%' }} />
              </div>
            </div>

            <div className="breakdown-row">
              <div className="breakdown-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                  <b>{t('stageOperations')}</b>
                </span>
                <span>10% · 4.2 kg</span>
              </div>
              <div className="breakdown-track">
                <div className="breakdown-fill fill-ops" style={{ width: '10%' }} />
              </div>
            </div>
          </div>

          <div style={{ marginTop: 20, width: '100%', background: '#f4f8f4', padding: 12, borderRadius: 10, fontSize: 11, color: '#5f7872', textAlign: 'left' }}>
            <b style={{ color: '#1a4947', display: 'block', marginBottom: 4 }}>💡 {t('didYouKnow')}</b>
            {t('didYouKnowText')}
          </div>
        </section>
      </div>
    </>
  );
}

function RouteShell({ children, adminOnly=false }:any){return <AppFrame adminOnly={adminOnly}>{children}</AppFrame>}
function AppRoutes() {
  const session=useGetAuthSession();
  if (session.isError && isNetworkFailure(session.error)) {
    return <ServerUnavailable retry={() => session.refetch()}/>;
  }
  return <>
  <AlertNotifications enabled={!!session.data?.user}/>
  <Routes>
    <Route path="/login" element={session.data?.user?<Navigate to="/dashboard" replace/>:<AuthPage/>}/>
    <Route path="/register" element={session.data?.user?<Navigate to="/dashboard" replace/>:<AuthPage register/>}/>
    <Route path="/" element={<Navigate to="/login" replace/>}/>
    <Route path="/dashboard" element={<RouteShell><Dashboard/></RouteShell>}/>
    <Route path="/sustainability" element={<RouteShell><SustainabilityPage/></RouteShell>}/>
    <Route path="/alerts" element={<RouteShell><Alerts/></RouteShell>}/>
    <Route path="/map" element={<RouteShell><PipelineMap/></RouteShell>}/>
    <Route path="/analytics" element={<RouteShell><AnalyticsPage/></RouteShell>}/>
    <Route path="/maintenance" element={<RouteShell><Maintenance/></RouteShell>}/>
    <Route path="/champions" element={<RouteShell><Champions/></RouteShell>}/>
    <Route path="/reports" element={<RouteShell><Reports/></RouteShell>}/>
    <Route path="/profile" element={<RouteShell><Profile/></RouteShell>}/>
    <Route path="/settings" element={<RouteShell adminOnly><SettingsPage/></RouteShell>}/>
    <Route path="/simulation" element={<RouteShell adminOnly><Simulation/></RouteShell>}/>
    <Route path="*" element={<main className="not-found"><div className="brand-mark"><Waves size={22}/></div><span className="eyebrow">404 · UNKNOWN ROUTE</span><h1 className="font-display">This route is off the map.</h1><NavLink to="/dashboard" className="btn btn-primary">Return to operations <ArrowRight size={16}/></NavLink></main>}/>
  </Routes></>;
}
function App() {
  return (
    <LanguageProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </LanguageProvider>
  );
}
export default App;
