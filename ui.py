import pygame
from constants import (
    BUTTON_COLOR,
    BUTTON_HOVER_COLOR,
    BUTTON_TEXT_COLOR,
    WHITE,
    TEXT_COLOR,
    GRAY,
    LINE_COLOR,
    BLACK
)


class Button:
    """A simple button class for Pygame UI."""

    def __init__(
        self,
        text,
        center_pos,
        font,
        base_color=BUTTON_COLOR,
        hover_color=BUTTON_HOVER_COLOR,
        text_color=BUTTON_TEXT_COLOR,
        width=None, # Optional width
        height=None, # Optional height
        color=WHITE,
        data=None
    ):
        self.text = text
        self.center_pos = center_pos
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovering = False
        self.data = data

        self.text_surf = self.font.render(self.text, True, self.text_color)

        # Determine button rectangle
        if width is not None and height is not None:
            # Use provided dimensions
            self.rect = pygame.Rect(0, 0, width, height)
            self.rect.center = self.center_pos
        elif width is not None:
            # Use provided width, calculate height based on text + padding
            text_height = self.text_surf.get_height()
            calculated_height = text_height + 20 # Add vertical padding
            self.rect = pygame.Rect(0, 0, width, calculated_height)
            self.rect.center = self.center_pos
        elif height is not None:
            # Use provided height, calculate width based on text + padding
            text_width = self.text_surf.get_width()
            calculated_width = text_width + 40 # Add horizontal padding
            self.rect = pygame.Rect(0, 0, calculated_width, height)
            self.rect.center = self.center_pos
        else:
            # Calculate dimensions based on text + padding (original behavior)
            self.rect = self.text_surf.get_rect(center=self.center_pos)
            self.rect.inflate_ip(40, 20) # Add padding (increased horizontal for consistency)

        # Center the text within the final button rectangle
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

    def draw(self, screen):
        """Draws the button on the screen."""
        current_color = self.hover_color if self.is_hovering else self.base_color
        pygame.draw.rect(screen, current_color, self.rect, border_radius=5)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 1, border_radius=5) # Outline
        screen.blit(self.text_surf, self.text_rect)

    def handle_event(self, event):
        """
        Handles mouse events for the button.
        Returns data if set and clicked, else text.
        """
        if event.type == pygame.MOUSEMOTION:
            self.is_hovering = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovering and event.button == 1:
                # If data attribute exists and is not None, return it
                if hasattr(self, 'data') and self.data is not None:
                    return self.data
                else:
                    return self.text # Otherwise, return the button text
        return None

class Checkbox:
    """A simple checkbox class."""
    def __init__(self, text, pos, font, initial_state=False, size=20, text_color=TEXT_COLOR, check_color=BLACK):
        self.text = text
        self.pos = pos # Top-left position
        self.font = font
        self.checked = initial_state
        self.size = size
        self.text_color = text_color
        self.check_color = check_color
        self.is_hovered = False

        # Create checkbox rectangle
        self.checkbox_rect = pygame.Rect(self.pos[0], self.pos[1], self.size, self.size)

        # Render text surface
        self.text_surface = self.font.render(self.text, True, self.text_color)
        # Position text to the right of the checkbox
        self.text_rect = self.text_surface.get_rect(midleft=(self.checkbox_rect.right + 10, self.checkbox_rect.centery))

        # Define the clickable area (checkbox + text)
        self.clickable_area = self.checkbox_rect.union(self.text_rect)

    def draw(self, screen):
        # Draw the box
        pygame.draw.rect(screen, self.text_color, self.checkbox_rect, 1) # Box outline
        # Draw the checkmark if checked
        if self.checked:
            pygame.draw.line(screen, self.check_color, self.checkbox_rect.topleft, self.checkbox_rect.bottomright, 2)
            pygame.draw.line(screen, self.check_color, self.checkbox_rect.topright, self.checkbox_rect.bottomleft, 2)
        # Draw the text label
        screen.blit(self.text_surface, self.text_rect)

    def handle_event(self, event):
        """Handles mouse events. Returns True if state changed, False otherwise."""
        state_changed = False
        if event.type == pygame.MOUSEMOTION:
             # Hover check could be added here if visual feedback is desired
             pass
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.clickable_area.collidepoint(event.pos):
                self.checked = not self.checked
                state_changed = True
        return state_changed


class Telop:
    """Displays temporary, animated text notifications (like a toast/telop)."""
    def __init__(self, screen_width, center_pos, font, fade_duration=500, bg_color=(0, 0, 0, 180), text_color=WHITE):
        self.screen_width = screen_width
        self.center_pos = center_pos
        self.font = font
        self.fade_duration = fade_duration
        self.bg_color = bg_color # Should have 4 components (R, G, B, A)
        self.text_color = text_color

        self.text = ""
        self.duration = 0 # How long to stay fully visible (ms). None means indefinite.
        self.active = False
        self.state = 'idle' # idle, fading_in, visible, fading_out
        self.start_time = 0
        self.current_alpha = 0
        self.text_surface = None
        self.text_rect = None
        self.bg_rect = None

    def show(self, text, duration): # duration in ms, None for indefinite
        """Starts showing the telop with the given text and duration. Appears instantly."""
        self.text = text
        self.duration = duration
        self.active = True
        self.state = 'visible' # <<< Start directly in visible state
        self.start_time = pygame.time.get_ticks() # For duration tracking
        self.current_alpha = 255 # <<< Appear instantly

        # 1. Pre-render text to get its size
        self.text_surface = self.font.render(self.text, True, self.text_color)
        temp_text_rect = self.text_surface.get_rect()

        # 2. Calculate background rect (full width, height based on text + padding)
        padding_y = 10 # Vertical padding
        bg_height = temp_text_rect.height + padding_y * 2
        bg_top = self.center_pos[1] - bg_height // 2
        self.bg_rect = pygame.Rect(0, bg_top, self.screen_width, bg_height)

        # 3. Center the text rect within the new background rect
        self.text_rect = self.text_surface.get_rect(center=self.bg_rect.center)

    def hide(self):
        """Starts the fade-out animation if the telop is active."""
        # Only start fading out if currently visible
        if self.active and self.state == 'visible':
            self.state = 'fading_out'
            self.start_time = pygame.time.get_ticks()
            # Alpha is already 255, will fade from there

    def update(self):
        """Updates the animation state and alpha. Returns True if active."""
        if not self.active:
            return False

        now = pygame.time.get_ticks()
        elapsed = now - self.start_time

        # Removed fading_in state logic

        if self.state == 'visible':
            # print(f"DEBUG Telop.update: Visible - elapsed={elapsed}, duration={self.duration}") # Comment out
            if self.duration is not None and elapsed >= self.duration:
                self.state = 'fading_out'
                self.start_time = now # Reset timer for fade out
                # print("DEBUG Telop.update: Visible -> Fading Out") # Comment out

        elif self.state == 'fading_out':
            if elapsed >= self.fade_duration:
                self.current_alpha = 0
                self.state = 'idle'
                self.active = False
                # print("DEBUG Telop.update: Fading Out -> Idle") # Comment out
            else:
                # Ensure alpha calculation is correct when starting fade-out
                self.current_alpha = int(255 * (1 - (elapsed / self.fade_duration)))
                self.current_alpha = max(0, min(255, self.current_alpha))
                # print(f"DEBUG Telop.update: Fading Out - elapsed={elapsed}, alpha={self.current_alpha}") # Comment out

        # Clamp alpha just in case (though should be handled above)
        # self.current_alpha = max(0, min(255, self.current_alpha))
        return self.active

    def draw(self, screen):
        """Draws the telop onto the screen with current alpha."""
        # print(f"DEBUG Telop.draw: active={self.active}, state={self.state}, alpha={self.current_alpha}, text='{self.text}'") # Comment out

        if not self.active or self.current_alpha == 0 or not self.text_surface:
            # print("DEBUG Telop.draw: Condition met to not draw.") # Comment out
            return

        # Create background surface with SRCALPHA
        bg_surface = pygame.Surface(self.bg_rect.size, pygame.SRCALPHA)

        # Calculate combined alpha for background fill
        # Background has its own alpha (bg_color[3]) modulated by fade alpha (current_alpha)
        combined_bg_alpha = int(self.bg_color[3] * (self.current_alpha / 255))
        fill_color = (*self.bg_color[:3], combined_bg_alpha)
        bg_surface.fill(fill_color)

        # Blit the text surface (copy) with fade alpha onto the background surface
        temp_text_surface = self.text_surface.copy()
        temp_text_surface.set_alpha(self.current_alpha)
        text_blit_pos = (self.text_rect.left - self.bg_rect.left,
                         self.text_rect.top - self.bg_rect.top)
        bg_surface.blit(temp_text_surface, text_blit_pos)

        # Blit the final combined surface onto the main screen
        screen.blit(bg_surface, self.bg_rect.topleft)


class TextPopup:
    """Displays temporary text near a specific location."""
    def __init__(self, text, target_pos, font, duration=1000, color=WHITE, offset_y=-30):
        self.text = text
        self.target_pos = target_pos # Center position of the target stone (pixels)
        self.font = font
        self.duration = float(duration) # Use float for division
        self.color = color
        self.initial_offset_y = offset_y # Starting vertical offset
        self.fade_move_distance = 20 # How many pixels it moves up during fade

        self.active = False
        self.start_time = 0.0
        self.text_surface = None
        self.text_rect = None
        self.current_alpha = 255.0
        self.current_offset_y = self.initial_offset_y

    def show(self):
        """Activates the popup."""
        self.text_surface = self.font.render(self.text, True, self.color)
        # Position the text centered horizontally, offset vertically
        popup_center_x = self.target_pos[0]
        popup_center_y = self.target_pos[1] + self.initial_offset_y # Use initial offset
        self.text_rect = self.text_surface.get_rect(center=(popup_center_x, popup_center_y))
        self.start_time = float(pygame.time.get_ticks())
        self.current_alpha = 255.0
        self.current_offset_y = self.initial_offset_y
        self.active = True

    def update(self):
        """Updates animation (fade out and move up). Returns False if duration passed."""
        if not self.active:
            return False

        now = float(pygame.time.get_ticks())
        elapsed = now - self.start_time

        if elapsed >= self.duration:
            self.active = False
            return False
        else:
            # Calculate progress (0.0 to 1.0)
            progress = elapsed / self.duration

            # Update alpha (linear fade out)
            self.current_alpha = 255.0 * (1.0 - progress)
            self.current_alpha = max(0.0, min(255.0, self.current_alpha)) # Clamp alpha

            # Update vertical offset (linear move up)
            self.current_offset_y = self.initial_offset_y - (self.fade_move_distance * progress)

            # Update the rect position based on the current offset
            popup_center_x = self.target_pos[0]
            popup_center_y = self.target_pos[1] + self.current_offset_y
            if self.text_rect: # Ensure text_rect exists before moving
                self.text_rect.center = (popup_center_x, popup_center_y)

            return True

    def draw(self, screen):
        """Draws the text popup if active with current alpha and position."""
        if self.active and self.text_surface and self.text_rect:
            # Create a temporary surface to apply alpha correctly
            temp_surface = self.text_surface.copy()
            temp_surface.set_alpha(int(self.current_alpha))
            # Optional: Add background later if needed
            screen.blit(temp_surface, self.text_rect)

    def adjust_position(self, dy):
        """Adjusts the vertical position (for stacking)."""
        if self.text_rect:
             self.text_rect.move_ip(0, dy) 