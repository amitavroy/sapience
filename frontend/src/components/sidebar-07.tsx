"use client";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Calendar,
  ChevronDown,
  ChevronRight,
  CreditCard,
  LogOut,
  Mail,
  MessageSquare,
  Plus,
  Settings,
  User,
  Users,
} from "lucide-react";

export function Sidebar07() {
  return (
    <div className="flex h-screen w-64 flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="flex h-16 items-center justify-between px-4">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
          Sapience
        </h1>
        <Button variant="ghost" size="icon">
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <Mail className="mr-2 h-4 w-4" />
            Inbox
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <Calendar className="mr-2 h-4 w-4" />
            Calendar
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            Messages
          </Button>
        </div>

        <Separator className="my-4" />

        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              TEAMS
            </span>
            <Button variant="ghost" size="icon" className="h-6 w-6">
              <Plus className="h-3 w-3" />
            </Button>
          </div>
          <div className="space-y-1">
            <Button
              variant="ghost"
              className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <ChevronRight className="mr-2 h-4 w-4" />
              <Users className="mr-2 h-4 w-4" />
              Engineering
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <ChevronRight className="mr-2 h-4 w-4" />
              <Users className="mr-2 h-4 w-4" />
              Design
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <ChevronDown className="mr-2 h-4 w-4" />
              <Users className="mr-2 h-4 w-4" />
              Marketing
            </Button>
            <div className="ml-6 space-y-1">
              <Button
                variant="ghost"
                className="w-full justify-start text-sm text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-800"
              >
                <User className="mr-2 h-3 w-3" />
                John Doe
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start text-sm text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-800"
              >
                <User className="mr-2 h-3 w-3" />
                Jane Smith
              </Button>
            </div>
          </div>
        </div>

        <Separator className="my-4" />

        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <CreditCard className="mr-2 h-4 w-4" />
            Billing
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start text-gray-700 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </div>
      </nav>

      <Separator />

      {/* User Profile */}
      <div className="p-4">
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-full bg-gray-300 dark:bg-gray-700"></div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              John Doe
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              john@example.com
            </p>
          </div>
          <Button variant="ghost" size="icon">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
