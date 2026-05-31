"use client"

import * as React from "react"
import {
  Controller,
  FormProvider,
  useFormContext,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
} from "react-hook-form"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

// ---------------------------------------------------------------------------
// Minimal Slot implementation (merges props onto single child element).
// This avoids a @radix-ui/react-slot dependency since this project uses
// @base-ui/react and @radix-ui is not installed.
// ---------------------------------------------------------------------------
type SlotProps = React.HTMLAttributes<HTMLElement> & {
  ref?: React.Ref<HTMLElement>
  children?: React.ReactNode
}

const Slot = React.forwardRef<HTMLElement, SlotProps>(
  ({ children, ...slotProps }, ref) => {
    if (!React.isValidElement(children)) {
      return null
    }
    // Merge the slot props onto the child, with child's own props taking
    // precedence for className and event handlers.
    const childProps = children.props as Record<string, unknown>
    const mergedProps: Record<string, unknown> = { ...slotProps, ...childProps }

    // Merge classNames
    if (slotProps.className && childProps.className) {
      mergedProps.className = cn(
        slotProps.className as string,
        childProps.className as string
      )
    }

    return React.cloneElement(children, { ...mergedProps, ref } as React.HTMLAttributes<HTMLElement> & { ref: React.Ref<HTMLElement> })
  }
)
Slot.displayName = "Slot"

// ---------------------------------------------------------------------------
// Form (re-export FormProvider under a shorter name)
// ---------------------------------------------------------------------------
const Form = FormProvider

// ---------------------------------------------------------------------------
// FormField context
// ---------------------------------------------------------------------------
type FormFieldContextValue<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> = {
  name: TName
}

const FormFieldContext = React.createContext<FormFieldContextValue>(
  {} as FormFieldContextValue
)

const FormField = <
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  ...props
}: ControllerProps<TFieldValues, TName>) => {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// FormItem context
// ---------------------------------------------------------------------------
type FormItemContextValue = {
  id: string
}

const FormItemContext = React.createContext<FormItemContextValue>(
  {} as FormItemContextValue
)

// ---------------------------------------------------------------------------
// useFormField hook
// ---------------------------------------------------------------------------
const useFormField = () => {
  const fieldContext = React.useContext(FormFieldContext)
  const itemContext = React.useContext(FormItemContext)
  const { getFieldState, formState } = useFormContext()

  if (!fieldContext) {
    throw new Error("useFormField should be used within <FormField>")
  }

  const fieldState = getFieldState(fieldContext.name, formState)
  const { id } = itemContext

  return {
    id,
    name: fieldContext.name,
    formItemId: `${id}-form-item`,
    formDescriptionId: `${id}-form-item-description`,
    formMessageId: `${id}-form-item-message`,
    ...fieldState,
  }
}

// ---------------------------------------------------------------------------
// FormItem
// ---------------------------------------------------------------------------
const FormItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const id = React.useId()

  return (
    <FormItemContext.Provider value={{ id }}>
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    </FormItemContext.Provider>
  )
})
FormItem.displayName = "FormItem"

// ---------------------------------------------------------------------------
// FormLabel
// ---------------------------------------------------------------------------
const FormLabel = React.forwardRef<
  HTMLLabelElement,
  React.ComponentProps<"label">
>(({ className, ...props }, ref) => {
  const { error, formItemId } = useFormField()

  return (
    <Label
      ref={ref}
      className={cn(error && "text-destructive", className)}
      htmlFor={formItemId}
      {...props}
    />
  )
})
FormLabel.displayName = "FormLabel"

// ---------------------------------------------------------------------------
// FormControl — uses the minimal Slot above to merge aria-* props onto child
// ---------------------------------------------------------------------------
const FormControl = React.forwardRef<
  HTMLElement,
  SlotProps
>(({ ...props }, ref) => {
  const { error, formItemId, formDescriptionId, formMessageId } = useFormField()

  return (
    <Slot
      ref={ref}
      id={formItemId}
      aria-describedby={
        !error
          ? `${formDescriptionId}`
          : `${formDescriptionId} ${formMessageId}`
      }
      aria-invalid={!!error}
      {...props}
    />
  )
})
FormControl.displayName = "FormControl"

// ---------------------------------------------------------------------------
// FormDescription
// ---------------------------------------------------------------------------
const FormDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => {
  const { formDescriptionId } = useFormField()

  return (
    <p
      ref={ref}
      id={formDescriptionId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
})
FormDescription.displayName = "FormDescription"

// ---------------------------------------------------------------------------
// FormMessage
// ---------------------------------------------------------------------------
const FormMessage = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  const { error, formMessageId } = useFormField()
  const body = error ? String(error?.message) : children

  if (!body) {
    return null
  }

  return (
    <p
      ref={ref}
      id={formMessageId}
      className={cn("text-sm font-medium text-destructive", className)}
      {...props}
    >
      {body}
    </p>
  )
})
FormMessage.displayName = "FormMessage"

export {
  useFormField,
  Form,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
}
