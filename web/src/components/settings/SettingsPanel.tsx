import type { AppConfig, JobSettings, UploadedSrt } from "../../api/types";
import { CLIP_LENGTH_LABELS, GENRE_LABELS, languageLabel } from "../../lib/labels";
import { AspectSelect } from "./AspectSelect";
import { CaptionGallery } from "./CaptionGallery";
import { ChipGroup } from "./ChipGroup";
import { Field } from "./Field";
import { RangeSlider } from "./RangeSlider";
import { Segmented } from "./Segmented";
import { SrtUpload } from "./SrtUpload";
import { Stepper } from "./Stepper";
import { Switch } from "./Switch";

interface Props {
  config: AppConfig;
  settings: JobSettings;
  duration: number;
  srtBusy: boolean;
  srtError: string | null;
  onChange: (patch: Partial<JobSettings>) => void;
  onSrtFile: (file: File) => void;
  onSrtRemove: () => void;
}

export function SettingsPanel({ config, settings, duration, srtBusy, srtError, onChange, onSrtFile, onSrtRemove }: Props) {
  const window: [number, number] = settings.time_range ?? [0, duration];
  const setWindow = ([lo, hi]: [number, number]) =>
    onChange({ time_range: lo <= 0 && hi >= duration ? null : [lo, hi] });
  const srt: UploadedSrt | null = settings.srt;
  return (
    <section className="panel" aria-label="Ajustes">
      <h2 className="panel-title">Ajustes</h2>
      <div className="settings-grid">
        <Field label="Modelo de selección">
          <Segmented
            label="Modelo"
            value={settings.model_tier}
            onChange={(model_tier) => onChange({ model_tier })}
            options={[
              { value: "powerful", label: "Potente", sub: config.models.powerful },
              { value: "light", label: "Ligero", sub: config.models.light },
            ]}
          />
        </Field>

        <Field label="Género" id="genre">
          <select id="genre" className="select" value={settings.genre} onChange={(e) => onChange({ genre: e.target.value })}>
            {config.genres.map((g) => (
              <option key={g} value={g}>
                {GENRE_LABELS[g] ?? g}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Duración de los clips" wide>
          <ChipGroup
            label="Duración de los clips"
            value={settings.clip_length}
            onChange={(clip_length) => onChange({ clip_length })}
            options={config.clip_lengths.map((v) => ({ value: v, label: CLIP_LENGTH_LABELS[v] ?? v }))}
          />
        </Field>

        <Field label="Número máximo de clips">
          <Stepper label="Número máximo de clips" min={1} max={20} value={settings.max_clips} onChange={(max_clips) => onChange({ max_clips })} />
        </Field>

        <Field label="Zoom automático" hint="Acercamientos suaves al inicio de las frases.">
          <div className="switch-row">
            <Switch label="Zoom automático" checked={settings.auto_zoom} onChange={(auto_zoom) => onChange({ auto_zoom })} />
            <span className="muted">{settings.auto_zoom ? "Activado" : "Desactivado"}</span>
          </div>
        </Field>

        <Field
          label="Momentos específicos"
          wide
          id="moments"
          hint="Describe lo que buscas o escribe rangos como 10:30-11:15"
        >
          <textarea
            id="moments"
            className="textarea"
            rows={3}
            placeholder="Ej.: cuando hablan de su primer disco, 10:40-11:35"
            value={settings.specific_moments}
            onChange={(e) => onChange({ specific_moments: e.target.value })}
          />
        </Field>

        {duration > 0 && (
          <Field label="Rango de procesamiento" wide hint="Solo se analizará esta parte del video.">
            <RangeSlider min={0} max={Math.floor(duration)} value={[Math.round(window[0]), Math.round(window[1])]} onChange={setWindow} />
          </Field>
        )}

        <Field label="Subtítulos" wide>
          <CaptionGallery presets={config.caption_presets} value={settings.caption_style} onChange={(caption_style) => onChange({ caption_style })} />
        </Field>

        <Field label="Relación de aspecto" id="aspect">
          <AspectSelect id="aspect" value={settings.aspect_ratio} options={config.aspect_ratios} onChange={(aspect_ratio) => onChange({ aspect_ratio })} />
        </Field>

        <Field label="Idioma" id="language">
          <select id="language" className="select" value={settings.language} onChange={(e) => onChange({ language: e.target.value })}>
            {config.languages.map((l) => (
              <option key={l.code} value={l.code}>
                {languageLabel(l.code, l.name)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Subtítulos propios (SRT)" wide>
          <SrtUpload srt={srt} busy={srtBusy} error={srtError} onFile={onSrtFile} onRemove={onSrtRemove} />
        </Field>
      </div>
    </section>
  );
}
