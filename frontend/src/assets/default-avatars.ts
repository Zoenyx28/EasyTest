export interface DefaultAvatar {
  id: string;
  svg: string;
  color: string;
}

export const defaultAvatars: DefaultAvatar[] = [
  {
    id: 'default:1',
    color: '#FF6B6B',
    svg: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#FF6B6B"/><text x="20" y="25" text-anchor="middle" fill="white" font-size="18" font-weight="bold">1</text></svg>`,
  },
  {
    id: 'default:2',
    color: '#4ECDC4',
    svg: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#4ECDC4"/><text x="20" y="25" text-anchor="middle" fill="white" font-size="18" font-weight="bold">2</text></svg>`,
  },
  {
    id: 'default:3',
    color: '#45B7D1',
    svg: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#45B7D1"/><text x="20" y="25" text-anchor="middle" fill="white" font-size="18" font-weight="bold">3</text></svg>`,
  },
  {
    id: 'default:4',
    color: '#96CEB4',
    svg: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#96CEB4"/><text x="20" y="25" text-anchor="middle" fill="white" font-size="18" font-weight="bold">4</text></svg>`,
  },
  {
    id: 'default:5',
    color: '#FFEAA7',
    svg: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="20" fill="#FFEAA7"/><text x="20" y="25" text-anchor="middle" fill="#333" font-size="18" font-weight="bold">5</text></svg>`,
  },
];