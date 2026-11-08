export function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const className =
    "mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base";
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      {multiline ? (
        <textarea
          rows={3}
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        />
      ) : (
        <input
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={className}
        />
      )}
    </label>
  );
}

export function StringListEditor({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <textarea
        rows={Math.max(3, values.length)}
        required
        value={values.join("\n")}
        onChange={(event) => onChange(event.target.value.split("\n"))}
        onBlur={() => onChange(values.map((value) => value.trim()).filter(Boolean))}
        className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base"
      />
      <span className="mt-1 block font-normal text-slate-500">
        Enter one outcome per line.
      </span>
    </label>
  );
}
