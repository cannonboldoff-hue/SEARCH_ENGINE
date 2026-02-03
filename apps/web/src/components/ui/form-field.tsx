"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type FormFieldProps = {
  id: string;
  label: string;
  error?: string;
  className?: string;
  inputClassName?: string;
} & React.ComponentProps<typeof Input>;

export const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(
  ({ id, label, error, className, inputClassName, ...inputProps }, ref) => (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} ref={ref} className={inputClassName} {...inputProps} />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
);
FormField.displayName = "FormField";
