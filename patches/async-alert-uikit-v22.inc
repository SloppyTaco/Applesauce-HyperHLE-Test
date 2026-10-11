/*
 * Applesauce V22: direct UIKit control events, not deferred UIAlertAction
 * dismissal handlers. The V20 SDL ABI and guest polling protocol are retained.
 * Copyright 2026 touchHLE contributors; SDL zlib license applies.
 */
#import <UIKit/UIKit.h>
#include <stdint.h>

@class TouchHLEAlertStateV20;
@interface TouchHLEAlertControllerV20 : UIViewController
@property(nonatomic) UIInterfaceOrientationMask orientationMask;
@property(nonatomic, weak) TouchHLEAlertStateV20 *alertState;
@property(nonatomic, copy) NSArray<UIButton *> *buttons;
@end

@interface TouchHLEAlertStateV20 : NSObject
@property(nonatomic) uint64_t token;
@property(nonatomic) NSInteger selectedIndex;
@property(nonatomic, copy) NSString *title;
@property(nonatomic, copy) NSString *message;
@property(nonatomic, copy) NSArray<NSString *> *buttonTitles;
@property(nonatomic, weak) UIWindow *parentWindow;
@property(nonatomic, weak) UIWindow *previousKeyWindow;
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) TouchHLEAlertControllerV20 *controller;
- (void)buttonTappedV22:(UIButton *)sender;
@end

static NSMutableDictionary<NSNumber *, TouchHLEAlertStateV20 *> *touchHLEAlertsV20;
static NSMutableArray<NSNumber *> *touchHLEAlertQueueV20;
static uint64_t touchHLEActiveAlertV20;
static uint64_t touchHLENextAlertV20 = 1;

static BOOL TouchHLE_AlertOnMainThreadV20(void)
{
    if ([NSThread isMainThread]) return YES;
    NSLog(@"[ALERT NATIVE v22] Refused off-main-thread alert operation");
    return NO;
}

static void TouchHLE_CloseAlertWindowV20(TouchHLEAlertStateV20 *state)
{
    BOOL wasKeyWindow = state.window.isKeyWindow;
    state.window.hidden = YES;
    state.window.rootViewController = nil;
    state.controller = nil;
    state.window = nil;
    UIWindow *previous = state.previousKeyWindow;
    if (wasKeyWindow && previous && !previous.hidden) [previous makeKeyWindow];
}

static void TouchHLE_RecordAlertSelectionV20(TouchHLEAlertStateV20 *state,
                                            NSInteger index)
{
    if (!TouchHLE_AlertOnMainThreadV20() || !state ||
        touchHLEAlertsV20[@(state.token)] != state ||
        state.token != touchHLEActiveAlertV20 || state.selectedIndex != -1 ||
        index < 0 || index >= (NSInteger)state.buttonTitles.count) return;
    state.selectedIndex = index;
    for (UIButton *button in state.controller.buttons) button.enabled = NO;
    NSLog(@"[ALERT NATIVE v22] Button %ld selected for token %llu via direct control event",
          (long)index, (unsigned long long)state.token);
}

@implementation TouchHLEAlertStateV20
- (void)buttonTappedV22:(UIButton *)sender
{
    if (![self.controller.buttons containsObject:sender]) return;
    TouchHLE_RecordAlertSelectionV20(self, sender.tag);
}
@end

@implementation TouchHLEAlertControllerV20
- (UIInterfaceOrientationMask)supportedInterfaceOrientations
{
    return self.orientationMask;
}
- (BOOL)shouldAutorotate { return NO; }
- (void)loadView
{
    UIView *background = [UIView new];
    background.backgroundColor = [UIColor.blackColor colorWithAlphaComponent:0.35];
    background.accessibilityIdentifier = @"touchHLE.alert.card.v22";
    self.view = background;
    UIView *card = [UIView new];
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.backgroundColor = UIColor.secondarySystemBackgroundColor;
    card.layer.cornerRadius = 20;
    card.clipsToBounds = YES;
    [background addSubview:card];
    UIScrollView *scroll = [UIScrollView new];
    scroll.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:scroll];
    UIStackView *stack = [UIStackView new];
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 14;
    [scroll addSubview:stack];
    TouchHLEAlertStateV20 *state = self.alertState;
    if (state.title.length) {
        UILabel *title = [UILabel new];
        title.text = state.title;
        title.font = [UIFont preferredFontForTextStyle:UIFontTextStyleHeadline];
        title.adjustsFontForContentSizeCategory = YES;
        title.textAlignment = NSTextAlignmentCenter;
        title.numberOfLines = 0;
        [stack addArrangedSubview:title];
    }
    if (state.message.length) {
        UILabel *message = [UILabel new];
        message.text = state.message;
        message.font = [UIFont preferredFontForTextStyle:UIFontTextStyleSubheadline];
        message.adjustsFontForContentSizeCategory = YES;
        message.textAlignment = NSTextAlignmentCenter;
        message.numberOfLines = 0;
        [stack addArrangedSubview:message];
    }
    NSMutableArray<UIButton *> *buttons = [NSMutableArray new];
    for (NSUInteger index = 0; index < state.buttonTitles.count; index++) {
        UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
        [button setTitle:state.buttonTitles[index] forState:UIControlStateNormal];
        button.tag = (NSInteger)index;
        button.titleLabel.font = [UIFont preferredFontForTextStyle:UIFontTextStyleHeadline];
        button.titleLabel.adjustsFontForContentSizeCategory = YES;
        button.titleLabel.numberOfLines = 0;
        button.backgroundColor = UIColor.tertiarySystemFillColor;
        button.layer.cornerRadius = 10;
        button.accessibilityIdentifier = [NSString stringWithFormat:@"touchHLE.alert.button.%lu", (unsigned long)index];
        [button.heightAnchor constraintGreaterThanOrEqualToConstant:48].active = YES;
        [button addTarget:state action:@selector(buttonTappedV22:) forControlEvents:UIControlEventTouchUpInside];
        [stack addArrangedSubview:button];
        [buttons addObject:button];
    }
    self.buttons = buttons;
    NSLayoutConstraint *naturalHeight = [card.heightAnchor constraintEqualToAnchor:stack.heightAnchor constant:36];
    naturalHeight.priority = UILayoutPriorityDefaultHigh;
    NSLayoutConstraint *preferredWidth = [card.widthAnchor constraintEqualToConstant:420];
    preferredWidth.priority = UILayoutPriorityDefaultHigh;
    [NSLayoutConstraint activateConstraints:@[
        [card.centerXAnchor constraintEqualToAnchor:background.safeAreaLayoutGuide.centerXAnchor],
        [card.centerYAnchor constraintEqualToAnchor:background.safeAreaLayoutGuide.centerYAnchor],
        [card.widthAnchor constraintLessThanOrEqualToAnchor:background.safeAreaLayoutGuide.widthAnchor constant:-32],
        [card.heightAnchor constraintLessThanOrEqualToAnchor:background.safeAreaLayoutGuide.heightAnchor constant:-32],
        [card.heightAnchor constraintGreaterThanOrEqualToConstant:84], preferredWidth, naturalHeight,
        [scroll.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:18],
        [scroll.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-18],
        [scroll.topAnchor constraintEqualToAnchor:card.topAnchor constant:18],
        [scroll.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-18],
        [stack.leadingAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.leadingAnchor],
        [stack.trailingAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.trailingAnchor],
        [stack.topAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.topAnchor],
        [stack.bottomAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.bottomAnchor],
        [stack.widthAnchor constraintEqualToAnchor:scroll.frameLayoutGuide.widthAnchor]
    ]];
}
@end

static void TouchHLE_PresentNextAlertV20(void)
{
    if (touchHLEActiveAlertV20) return;
    while (touchHLEAlertQueueV20.count) {
        NSNumber *key = touchHLEAlertQueueV20.firstObject;
        [touchHLEAlertQueueV20 removeObjectAtIndex:0];
        TouchHLEAlertStateV20 *state = touchHLEAlertsV20[key];
        if (!state) continue;
        UIWindowScene *scene = state.parentWindow.windowScene;
        if (!scene) {
            for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
                if ([candidate isKindOfClass:[UIWindowScene class]] &&
                    candidate.activationState == UISceneActivationStateForegroundActive) {
                    scene = (UIWindowScene *)candidate;
                    break;
                }
            }
        }
        if (!scene) { state.selectedIndex = -2; continue; }
        for (UIWindow *candidate in scene.windows) {
            if (candidate.isKeyWindow) { state.previousKeyWindow = candidate; break; }
        }
        if (!state.previousKeyWindow) state.previousKeyWindow = state.parentWindow;
        TouchHLEAlertControllerV20 *root = [TouchHLEAlertControllerV20 new];
        root.orientationMask = UIInterfaceOrientationIsLandscape(scene.interfaceOrientation)
            ? UIInterfaceOrientationMaskLandscape : UIInterfaceOrientationMaskPortrait;
        root.alertState = state;
        UIWindow *window = [[UIWindow alloc] initWithWindowScene:scene];
        window.frame = scene.coordinateSpace.bounds;
        window.backgroundColor = UIColor.clearColor;
        window.windowLevel = UIWindowLevelAlert + 1;
        window.rootViewController = root;
        window.accessibilityIdentifier = @"touchHLE.asyncAlert.v22";
        state.window = window;
        state.controller = root;
        touchHLEActiveAlertV20 = state.token;
        [window makeKeyAndVisible];
        [root.view layoutIfNeeded];
        NSLog(@"[ALERT NATIVE v22] Presented token %llu with %lu direct-action buttons above game controls",
              (unsigned long long)state.token, (unsigned long)state.buttonTitles.count);
        return;
    }
}

static uint64_t TouchHLE_BeginAsyncAlertV20(UIWindow *parent,
    const char *title, const char *message, const char *const *buttons, int count)
{
    if (!TouchHLE_AlertOnMainThreadV20() || !buttons || count < 1 || count > 256) return 0;
    if (!touchHLEAlertsV20) {
        touchHLEAlertsV20 = [NSMutableDictionary new];
        touchHLEAlertQueueV20 = [NSMutableArray new];
    }
    if (!touchHLENextAlertV20) return 0;
    TouchHLEAlertStateV20 *state = [TouchHLEAlertStateV20 new];
    state.token = touchHLENextAlertV20++;
    state.selectedIndex = -1;
    state.parentWindow = parent;
    state.title = title ? ([NSString stringWithUTF8String:title] ?: @"") : @"";
    state.message = message ? ([NSString stringWithUTF8String:message] ?: @"") : @"";
    NSMutableArray<NSString *> *titles = [NSMutableArray arrayWithCapacity:count];
    for (int index = 0; index < count; index++) {
        NSString *text = buttons[index] ? [NSString stringWithUTF8String:buttons[index]] : nil;
        [titles addObject:text ?: @""];
    }
    state.buttonTitles = titles;
    touchHLEAlertsV20[@(state.token)] = state;
    [touchHLEAlertQueueV20 addObject:@(state.token)];
    TouchHLE_PresentNextAlertV20();
    return state.token;
}

static void TouchHLE_DismissAsyncAlertV20(uint64_t token)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return;
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    if (!state) return;
    [touchHLEAlertQueueV20 removeObject:@(token)];
    if (touchHLEActiveAlertV20 == token) {
        TouchHLE_CloseAlertWindowV20(state);
        touchHLEActiveAlertV20 = 0;
    }
    [touchHLEAlertsV20 removeObjectForKey:@(token)];
    TouchHLE_PresentNextAlertV20();
}

static int TouchHLE_PollAsyncAlertV20(uint64_t token)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return -2;
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    if (!state) return -2;
    int result = (int)state.selectedIndex;
    if (result != -1) TouchHLE_DismissAsyncAlertV20(token);
    return result;
}

static void TouchHLE_ResetAsyncAlertsV20(void)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return;
    TouchHLEAlertStateV20 *active = touchHLEAlertsV20[@(touchHLEActiveAlertV20)];
    if (active) TouchHLE_CloseAlertWindowV20(active);
    touchHLEActiveAlertV20 = 0;
    [touchHLEAlertQueueV20 removeAllObjects];
    [touchHLEAlertsV20 removeAllObjects];
}
