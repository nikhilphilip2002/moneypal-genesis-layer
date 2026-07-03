'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';

/* ═══════════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════════ */

export interface WordCloudItem {
    label: string;
    value: number;
    tooltip?: string;
    code?: string;
}

interface PlacedWord {
    text: string;
    x: number;
    y: number;
    fontSize: number;
    color: string;
    rotation: number; // 0 or 90
    width: number;
    height: number;
    item: WordCloudItem;
}

interface TooltipState {
    text: string;
    x: number;
    y: number;
}

/* ═══════════════════════════════════════════════════════════════════════════
   PALETTES  (readable on both light & dark backgrounds)
   ═══════════════════════════════════════════════════════════════════════════ */

const PALETTES = {
    cool: [
        '#2563EB', '#7C3AED', '#0891B2', '#059669', '#6366F1',
        '#0D9488', '#4F46E5', '#047857', '#1D4ED8', '#8B5CF6',
        '#0EA5E9', '#10B981',
    ],
    warm: [
        '#DC2626', '#EA580C', '#D97706', '#BE185D', '#9333EA',
        '#E11D48', '#C026D3', '#B91C1C', '#F59E0B', '#DB2777',
        '#EF4444', '#F97316',
    ],
};

/* ═══════════════════════════════════════════════════════════════════════════
   PIXEL-MASK COLLISION LAYOUT
   ═══════════════════════════════════════════════════════════════════════════ */

const FONT_FAMILY = 'Inter, system-ui, -apple-system, sans-serif';
const MIN_FONT = 14;
const MAX_FONT = 56;
const PAD = 4;

function getTextMetrics(
    text: string,
    fontSize: number,
    rotation: number,
): { w: number; h: number } {
    if (typeof document === 'undefined') {
        const charW = fontSize * 0.6 * text.length;
        return rotation === 90
            ? { w: fontSize + PAD * 2, h: charW + PAD * 2 }
            : { w: charW + PAD * 2, h: fontSize + PAD * 2 };
    }
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d')!;
    ctx.font = `bold ${fontSize}px ${FONT_FAMILY}`;
    const m = ctx.measureText(text);
    const tw = m.width + PAD * 2;
    const th = fontSize * 1.2 + PAD * 2;
    return rotation === 90 ? { w: th, h: tw } : { w: tw, h: th };
}

/**
 * Lay out words using an Archimedean spiral with bounding-box collision.
 * Sorted largest-first so the biggest words get central placement.
 */
function layoutWords(
    items: WordCloudItem[],
    canvasW: number,
    canvasH: number,
    palette: string[],
): PlacedWord[] {
    if (!items.length || canvasW < 50) return [];

    const sorted = [...items].sort((a, b) => b.value - a.value);
    const minVal = Math.min(...sorted.map((i) => i.value));
    const maxVal = Math.max(...sorted.map((i) => i.value));
    const range = maxVal - minVal || 1;

    const placed: PlacedWord[] = [];
    const occupied: { x: number; y: number; w: number; h: number }[] = [];

    for (let i = 0; i < sorted.length; i++) {
        const item = sorted[i];
        const t = (item.value - minVal) / range;
        // logarithmic scaling for better visual distribution
        const fontSize = Math.round(MIN_FONT + Math.pow(t, 0.7) * (MAX_FONT - MIN_FONT));
        const color = palette[i % palette.length];
        const rotation = Math.random() < 0.6 ? 0 : 90;
        const displayText = item.code ? `${item.label} (${item.code})` : item.label;
        const { w, h } = getTextMetrics(displayText, fontSize, rotation);

        let bestX = canvasW / 2 - w / 2;
        let bestY = canvasH / 2 - h / 2;
        let found = false;

        // Archimedean spiral — tighter step for denser packing
        const maxAngle = Math.max(300, canvasW);
        for (let angle = 0; angle < maxAngle; angle += 0.3) {
            const r = 3.5 * angle;
            const cx = canvasW / 2 + r * Math.cos(angle) - w / 2;
            const cy = canvasH / 2 + r * Math.sin(angle) - h / 2;

            if (cx < 1 || cy < 1 || cx + w > canvasW - 1 || cy + h > canvasH - 1) continue;

            const overlaps = occupied.some(
                (o) => cx < o.x + o.w + 2 && cx + w + 2 > o.x && cy < o.y + o.h + 2 && cy + h + 2 > o.y,
            );

            if (!overlaps) {
                bestX = cx;
                bestY = cy;
                found = true;
                break;
            }
        }

        if (found) {
            occupied.push({ x: bestX, y: bestY, w, h });
            placed.push({
                text: displayText,
                x: bestX,
                y: bestY,
                fontSize,
                color,
                rotation,
                width: w,
                height: h,
                item,
            });
        }
    }

    return placed;
}

/* ═══════════════════════════════════════════════════════════════════════════
   CANVAS WORD CLOUD COMPONENT
   ═══════════════════════════════════════════════════════════════════════════ */

export interface WordCloudProps {
    items: WordCloudItem[];
    palette?: 'cool' | 'warm';
    emptyMessage?: string;
    onWordClick?: (item: WordCloudItem) => void;
}

export function WordCloud({
    items,
    palette = 'cool',
    emptyMessage = 'No data available.',
    onWordClick,
}: WordCloudProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [tooltip, setTooltip] = useState<TooltipState | null>(null);
    const [words, setWords] = useState<PlacedWord[]>([]);
    const [dims, setDims] = useState({ w: 600, h: 240 });
    const [opacity, setOpacity] = useState(0);

    // Responsive sizing — landscape ratio ~2.5:1
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;
        const ro = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const width = Math.floor(entry.contentRect.width);
                const height = Math.max(200, Math.min(360, Math.floor(width / 2.5)));
                setDims({ w: width, h: height });
            }
        });
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    // Layout words when items or dimensions change
    useEffect(() => {
        if (dims.w > 50 && items.length) {
            const colors = PALETTES[palette];
            setOpacity(0);
            setWords(layoutWords(items, dims.w, dims.h, colors));
            // Fade-in animation
            requestAnimationFrame(() => {
                requestAnimationFrame(() => setOpacity(1));
            });
        } else {
            setWords([]);
        }
    }, [items, dims, palette]);

    // Paint canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !words.length) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = dims.w * dpr;
        canvas.height = dims.h * dpr;
        canvas.style.width = `${dims.w}px`;
        canvas.style.height = `${dims.h}px`;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, dims.w, dims.h);

        for (const word of words) {
            ctx.save();
            ctx.font = `bold ${word.fontSize}px ${FONT_FAMILY}`;
            ctx.fillStyle = word.color;
            ctx.textBaseline = 'top';

            if (word.rotation === 90) {
                // Rotate around the center of the bounding box
                const cx = word.x + word.width / 2;
                const cy = word.y + word.height / 2;
                ctx.translate(cx, cy);
                ctx.rotate(Math.PI / 2);
                ctx.fillText(word.text, -word.height / 2 + PAD, -word.width / 2 + PAD);
            } else {
                ctx.fillText(word.text, word.x + PAD, word.y + PAD);
            }
            ctx.restore();
        }
    }, [words, dims]);

    // Hit-testing for hover & click
    const findHit = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>): PlacedWord | undefined => {
            const rect = canvasRef.current?.getBoundingClientRect();
            if (!rect) return;
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            // Reverse order so topmost (last painted) is checked first
            for (let i = words.length - 1; i >= 0; i--) {
                const w = words[i];
                if (mx >= w.x && mx <= w.x + w.width && my >= w.y && my <= w.y + w.height) {
                    return w;
                }
            }
            return undefined;
        },
        [words],
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const hit = findHit(e);
            const rect = canvasRef.current?.getBoundingClientRect();
            if (hit && hit.item.tooltip && rect) {
                setTooltip({
                    text: `${hit.text} (×${hit.item.value}) — ${hit.item.tooltip}`,
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top,
                });
            } else {
                setTooltip(null);
            }
        },
        [findHit],
    );

    const handleClick = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const hit = findHit(e);
            if (hit && onWordClick) {
                onWordClick(hit.item);
            }
        },
        [findHit, onWordClick],
    );

    if (!items.length) {
        return (
            <div className="flex items-center justify-center rounded-lg border bg-muted/30 py-12">
                <p className="text-sm text-muted-foreground">{emptyMessage}</p>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="relative w-full">
            <canvas
                ref={canvasRef}
                onMouseMove={handleMouseMove}
                onMouseLeave={() => setTooltip(null)}
                onClick={handleClick}
                className="w-full rounded-lg border bg-muted/20 transition-opacity duration-500"
                style={{ height: dims.h, cursor: onWordClick ? 'pointer' : 'crosshair', opacity }}
            />
            {tooltip && (
                <div
                    className="absolute z-50 max-w-xs rounded-md border bg-popover px-3 py-2 text-sm
                     text-popover-foreground shadow-md pointer-events-none"
                    style={{
                        left: Math.min(tooltip.x + 12, dims.w - 220),
                        top: Math.max(tooltip.y - 44, 4),
                    }}
                >
                    {tooltip.text}
                </div>
            )}
        </div>
    );
}
