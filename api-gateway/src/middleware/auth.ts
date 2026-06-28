import { Request, Response, NextFunction } from 'express'

export interface AuthRequest extends Request {
  userId?: string
  userRole?: string
}

// Auth disabled — all routes are publicly accessible
export function authenticate(_req: AuthRequest, _res: Response, next: NextFunction) {
  next()
}

export function authorize(..._roles: string[]) {
  return (_req: AuthRequest, _res: Response, next: NextFunction) => {
    next()
  }
}
