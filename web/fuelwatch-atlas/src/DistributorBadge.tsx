import { Fuel } from 'lucide-react';
import { distributorVisual } from './data';

type Props = {
  distributor?: string;
  size?: 'sm' | 'md' | 'lg';
};

export default function DistributorBadge({ distributor, size = 'md' }: Props) {
  const vis = distributorVisual(distributor);

  return (
    <span
      className={`dist-tile dist-tile-${size} ${vis.isWhiteLabel ? 'is-white-label' : ''}`}
      style={{
        backgroundColor: vis.bg,
        color: vis.fg,
        borderColor: vis.isWhiteLabel ? '#CBD5E1' : 'transparent',
      }}
      title={vis.label}
      aria-label={`Bandeira ${vis.label}`}
    >
      {vis.isWhiteLabel ? (
        <>
          <Fuel size={size === 'sm' ? 12 : size === 'lg' ? 18 : 15} strokeWidth={2.2} />
          {size !== 'sm' && <small>BRANCA</small>}
        </>
      ) : (
        <>
          {vis.accent && (
            <i className="dist-tile-stripe" style={{ backgroundColor: vis.accent }} />
          )}
          <strong>{vis.short}</strong>
        </>
      )}
    </span>
  );
}
