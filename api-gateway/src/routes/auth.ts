import { Router, Request, Response } from 'express'
import bcrypt from 'bcryptjs'
import jwt, { type SignOptions } from 'jsonwebtoken'
import { config } from '../config/index.js'
import { authenticate, AuthRequest } from '../middleware/auth.js'
import { Pool } from 'pg'

const router = Router()

export function createAuthRouter(pool: Pool) {
  router.post('/login', async (req: Request, res: Response) => {
    try {
      const { username, password } = req.body

      const result = await pool.query(
        'SELECT id, username, display_name, password_hash, role, is_active FROM users WHERE username = $1 AND is_active = true',
        [username]
      )

      if (result.rows.length === 0) {
        return res.status(401).json({ message: 'Invalid credentials', code: 'INVALID_CREDENTIALS' })
      }

      const user = result.rows[0]
      const isValid = await bcrypt.compare(password, user.password_hash)

      if (!isValid) {
        return res.status(401).json({ message: 'Invalid credentials', code: 'INVALID_CREDENTIALS' })
      }

      const signOpts: SignOptions = { expiresIn: 86400 }
      const token = jwt.sign({ userId: user.id, role: user.role }, config.jwtSecret, signOpts)

      const refreshOpts: SignOptions = { expiresIn: 604800 }
      const refreshToken = jwt.sign({ userId: user.id }, config.jwtSecret + '-refresh', refreshOpts)

      res.json({
        token,
        refreshToken,
        user: {
          id: user.id,
          username: user.username,
          displayName: user.display_name,
          role: user.role,
        },
      })
    } catch (error) {
      console.error('Login error:', error)
      res.status(500).json({ message: 'Login failed', code: 'LOGIN_FAILED' })
    }
  })

  router.get('/me', authenticate, async (req: AuthRequest, res: Response) => {
    try {
      const result = await pool.query(
        'SELECT id, username, display_name, email, role, is_active, created_at FROM users WHERE id = $1',
        [req.userId]
      )

      if (result.rows.length === 0) {
        return res.status(404).json({ message: 'User not found', code: 'USER_NOT_FOUND' })
      }

      const user = result.rows[0]
      res.json({
        id: user.id,
        username: user.username,
        displayName: user.display_name,
        email: user.email,
        role: user.role,
        isActive: user.is_active,
        createdAt: user.created_at,
      })
    } catch (error) {
      console.error('Get profile error:', error)
      res.status(500).json({ message: 'Failed to get profile', code: 'PROFILE_FAILED' })
    }
  })

  return router
}
