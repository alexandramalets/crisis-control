const SIZE = 16;

function Svg({ children, size = SIZE, label }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
    >
      {children}
    </svg>
  );
}

export function IconHome(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 7.5 8 2.5l5.5 5" />
      <path d="M4 7v6.5h8V7" />
    </Svg>
  );
}

export function IconData(props) {
  return (
    <Svg {...props}>
      <ellipse cx="8" cy="4" rx="5" ry="1.8" />
      <path d="M3 4v8c0 1 2.2 1.8 5 1.8s5-.8 5-1.8V4" />
      <path d="M3 8c0 1 2.2 1.8 5 1.8s5-.8 5-1.8" />
    </Svg>
  );
}

export function IconAnalysis(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 13V8.5" />
      <path d="M6.5 13V3.5" />
      <path d="M10.5 13V6.5" />
      <path d="M13.5 13V5" />
    </Svg>
  );
}

export function IconReports(props) {
  return (
    <Svg {...props}>
      <path d="M4 2.5h6l3.5 3.5V13.5H4z" />
      <path d="M10 2.5V6h3.5" />
      <path d="M6 9h4.5M6 11.5h3" />
    </Svg>
  );
}

export function IconSettings(props) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 2.5v1.6M8 11.9v1.6M2.5 8h1.6M11.9 8h1.6M4.1 4.1l1.1 1.1M10.8 10.8l1.1 1.1M11.9 4.1l-1.1 1.1M5.2 10.8l-1.1 1.1" />
    </Svg>
  );
}

export function IconHelp(props) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M6.2 6.2a1.8 1.8 0 1 1 2.3 2.2c-.6.3-1 .8-1 1.4" />
      <path d="M8 11.4v.2" />
    </Svg>
  );
}

export function IconMenu(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
    </Svg>
  );
}

export function IconClose(props) {
  return (
    <Svg {...props}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </Svg>
  );
}

export function IconChevron(props) {
  return (
    <Svg {...props}>
      <path d="M4 6l4 4 4-4" />
    </Svg>
  );
}

export function IconUser(props) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="5.5" r="2.3" />
      <path d="M3.2 13c.7-2.3 2.5-3.5 4.8-3.5s4.1 1.2 4.8 3.5" />
    </Svg>
  );
}

export function IconArrowUp(props) {
  return (
    <Svg {...props}>
      <path d="M8 12.5V3.5M4.5 7 8 3.5 11.5 7" />
    </Svg>
  );
}

export function IconArrowDown(props) {
  return (
    <Svg {...props}>
      <path d="M8 3.5v9M4.5 9 8 12.5 11.5 9" />
    </Svg>
  );
}

export function IconWarning(props) {
  return (
    <Svg {...props}>
      <path d="M8 2.8 14.2 13.5H1.8z" />
      <path d="M8 6.5v3.2M8 11.4v.3" />
    </Svg>
  );
}

export function IconInfo(props) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 7.2V11.5M8 5v.3" />
    </Svg>
  );
}

export function IconPlus(props) {
  return (
    <Svg {...props}>
      <path d="M8 3.5v9M3.5 8h9" />
    </Svg>
  );
}

export function IconSearch(props) {
  return (
    <Svg {...props}>
      <circle cx="7" cy="7" r="3.5" />
      <path d="M9.8 9.8 13 13" />
    </Svg>
  );
}

export function IconCheck(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 8.2 6.5 11.2 12.5 4.8" />
    </Svg>
  );
}

export function IconStatus(props) {
  return (
    <Svg {...props}>
      <path d="M3 10.5 6.2 7.3l2.3 2.3L13 5" />
    </Svg>
  );
}

export function IconCalendar(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 4.5h9v9h-9z" />
      <path d="M3.5 7h9M6 3.2v2.2M10 3.2v2.2" />
    </Svg>
  );
}

export function IconBuilding(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 13.5V4.5h6v9" />
      <path d="M9.5 7.5h3v6" />
      <path d="M5.5 6.5h1.2M5.5 9h1.2M5.5 11.5h1.2" />
    </Svg>
  );
}

export function IconRevenue(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="8" width="3" height="5.5" rx="0.6" />
      <rect x="6.5" y="5.5" width="3" height="8" rx="0.6" />
      <rect x="10.5" y="3" width="3" height="10.5" rx="0.6" />
    </Svg>
  );
}

export function IconProfit(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 11.5 6 7.5l2.5 2.5 5-6" />
      <path d="M9.5 4h4v4" />
    </Svg>
  );
}

export function IconReceivables(props) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="6" r="2.2" />
      <circle cx="10.5" cy="6.5" r="2.2" />
      <path d="M2.8 13c.6-2 2.1-3 4-3 1.2 0 2.2.4 3 1.1" />
      <path d="M9.2 13c.4-1.3 1.5-2.1 2.9-2.1 1.5 0 2.6.8 3.1 2.1" />
    </Svg>
  );
}

export function IconCash(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="4.5" width="11" height="7.5" rx="1.4" />
      <circle cx="8" cy="8.2" r="1.6" />
      <path d="M4.2 13h7.6" />
    </Svg>
  );
}
